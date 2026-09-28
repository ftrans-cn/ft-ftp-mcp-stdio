from __future__ import annotations

import fnmatch
import hashlib
import os
import posixpath
import secrets
import shutil
import stat
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, TypeVar, cast

from .credentials import get_optional_passphrase, get_password
from .drivers.base import Driver, Entry, FileInfo
from .drivers.ftp import FTPDriver
from .drivers.sftp import SFTPDriver
from .errors import AppError, map_exception
from .models import AppConfig, ServerConfig
from .paths import (
    join_remote_child,
    map_virtual_path,
    normalize_remote_path,
    validate_local_component,
    validate_writable,
)

T = TypeVar("T")
_REPARSE_POINT = 0x400


@dataclass
class _WriteAttempt:
    dispatched: bool = False

    def dispatch(self) -> None:
        self.dispatched = True


class FileService:
    def __init__(self, config: AppConfig, driver_factory: Callable[[ServerConfig, str], Driver] | None = None) -> None:
        self.config = config
        self._driver_factory = driver_factory

    def list_servers(self) -> dict[str, object]:
        return {"ok": True, "servers": [{"alias": s.alias, "description": s.description, "protocol": s.protocol, "read_only": s.read_only, "is_default": s.alias == self.config.default_server} for s in self.config.servers.values()]}

    def server(self, alias: str | None) -> ServerConfig:
        name = alias or self.config.default_server
        if name is None:
            raise AppError("invalid_config", "未配置默认服务器", "请调用 list_servers 选择服务器。")
        try:
            return self.config.servers[name]
        except KeyError as exc:
            raise AppError("not_found", "指定的服务器别名不存在", "请调用 list_servers 查看可用服务器。") from exc

    def _driver(self, server: ServerConfig) -> Driver:
        password, _ = self._credential(server)
        if self._driver_factory:
            return self._driver_factory(server, password or "")
        if server.protocol == "ftp":
            return FTPDriver(server, password or "")
        return SFTPDriver(server, password or "", self.config.config_path.parent / "known_hosts")

    @staticmethod
    def _credential(server: ServerConfig) -> tuple[str | None, str]:
        return get_optional_passphrase(server) if server.protocol == "sftp" and server.key_path else get_password(server)

    def _run_read(self, server: ServerConfig, action: Callable[[Driver], T], operation: str) -> T:
        last: AppError | None = None
        for attempt in range(2):
            driver: Driver | None = None
            try:
                driver = self._driver(server)
                return action(driver)
            except AppError as exc:
                last = exc
                if exc.error_type not in {"server_error", "connection_unavailable"} or attempt:
                    raise
            except Exception as exc:
                last = map_exception(exc, operation)
                if last.error_type not in {"server_error", "connection_unavailable"} or attempt:
                    raise last from exc
            finally:
                if driver is not None:
                    driver.close()
        assert last is not None
        raise last

    def _run_write(self, server: ServerConfig, action: Callable[[Driver, _WriteAttempt], T], operation: str) -> T:
        last: AppError | None = None
        for retry in range(2):
            driver: Driver | None = None
            attempt = _WriteAttempt()
            try:
                driver = self._driver(server)
                return action(driver, attempt)
            except AppError as exc:
                last = exc
                if exc.error_type == "connection_unavailable" and not attempt.dispatched and retry == 0:
                    continue
                raise
            except Exception as exc:
                last = map_exception(exc, operation)
                if last.error_type == "connection_unavailable" and not attempt.dispatched and retry == 0:
                    continue
                raise last from exc
            finally:
                if driver is not None:
                    driver.close()
        assert last is not None
        raise last

    def test_connection(self, alias: str | None = None) -> dict[str, object]:
        server = self.server(alias)
        return self._run_read(server, lambda driver: {"ok": True, "server": server.alias, "protocol": server.protocol, "read_only": server.read_only}, "测试连接")

    def list_dir(self, path: str, alias: str | None = None) -> dict[str, object]:
        server = self.server(alias)
        virtual = normalize_remote_path(path)
        remote = map_virtual_path(server, virtual)
        def action(driver: Driver) -> dict[str, object]:
            _check_remote(driver, remote, server.root)
            entries = driver.list_dir(remote)
            for item in entries:
                join_remote_child(virtual, item.name)
            return {"ok": True, "path": virtual, "entries": [_entry(item) for item in entries[:500]], "truncated": len(entries) > 500}
        return self._run_read(server, action, "列出目录")

    def search_files(self, path: str, pattern: str, alias: str | None = None) -> dict[str, object]:
        if not pattern or "/" in pattern or "\\" in pattern:
            raise AppError("invalid_argument", "pattern 必须是非空文件名通配符且不能包含路径分隔符")
        server = self.server(alias)
        virtual_start = normalize_remote_path(path)
        remote_start = map_virtual_path(server, virtual_start)
        matches: list[dict[str, object]] = []
        total = 0
        def action(driver: Driver) -> dict[str, object]:
            nonlocal total
            _check_remote(driver, remote_start, server.root)
            def walk(remote_parent: str, virtual_parent: str, depth: int) -> None:
                nonlocal total
                for entry in driver.list_dir(remote_parent):
                    remote_child = join_remote_child(remote_parent, entry.name)
                    virtual_child = join_remote_child(virtual_parent, entry.name)
                    if entry.type != "symlink" and fnmatch.fnmatchcase(entry.name, pattern):
                        total += 1
                        if len(matches) < 50:
                            matches.append({"path": virtual_child, "type": _object_type(entry.type), "size": entry.size, "mtime": entry.mtime})
                    if entry.type == "dir" and depth < 5:
                        walk(remote_child, virtual_child, depth + 1)
            walk(remote_start, virtual_start, 0)
            return {"ok": True, "path": virtual_start, "matches": matches, "truncated": total > len(matches)}
        return self._run_read(server, action, "搜索文件")

    def get_file_info(self, path: str, alias: str | None = None) -> dict[str, object]:
        server = self.server(alias)
        virtual = normalize_remote_path(path)
        remote = map_virtual_path(server, virtual)
        def action(driver: Driver) -> dict[str, object]:
            _check_remote(driver, remote, server.root)
            return _info_result(driver.get_info(remote), virtual)
        return self._run_read(server, action, "获取文件信息")

    def read_text_preview(self, path: str, max_bytes: int = 102400, alias: str | None = None) -> dict[str, object]:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or not 1 <= max_bytes <= 1048576:
            raise AppError("policy_rejected", "max_bytes 必须是 1 到 1048576 之间的整数")
        server = self.server(alias)
        virtual = normalize_remote_path(path)
        remote = map_virtual_path(server, virtual)
        def action(driver: Driver) -> dict[str, object]:
            _check_remote(driver, remote, server.root)
            info = driver.get_info(remote)
            if info.type != "file":
                raise AppError("policy_rejected", "目标不是文本文件")
            raw = driver.read_prefix(remote, max_bytes)
            truncated = len(raw) > max_bytes or (info.size is not None and info.size > max_bytes)
            content, encoding, partial = _decode_preview(raw[:max_bytes], truncated)
            returned = len(content.splitlines())
            return {"ok": True, "path": virtual, "content": content, "encoding": encoding, "truncated": truncated, "returned_lines": returned, "total_lines": None if truncated else returned, "partial_line": partial}
        return self._run_read(server, action, "读取文本预览")

    def download_file(self, remote_path: str, alias: str | None = None) -> dict[str, object]:
        server = self.server(alias)
        virtual = normalize_remote_path(remote_path)
        remote = map_virtual_path(server, virtual)
        name = posixpath.basename(virtual)
        validate_local_component(name)
        target_dir = self.config.staging_dir / uuid.uuid4().hex
        target = target_dir / name
        target_dir.mkdir(parents=True, exist_ok=False)
        try:
            def action(driver: Driver) -> dict[str, object]:
                _check_remote(driver, remote, server.root)
                before = driver.get_info(remote)
                if before.type != "file":
                    raise AppError("policy_rejected", "目标不是文件")
                try:
                    with target.open("xb") as handle:
                        downloaded = driver.download(remote, handle)
                except BaseException:
                    target.unlink(missing_ok=True)
                    raise
                actual = target.stat().st_size
                if before.size is not None and actual != before.size:
                    target.unlink(missing_ok=True)
                    raise AppError("integrity_check_failed", "下载结果未通过完整性检查")
                if _source_changed(before, driver.get_info(remote)):
                    target.unlink(missing_ok=True)
                    raise AppError("integrity_check_failed", "下载期间远端来源发生变化，结果未通过完整性检查")
                return {"ok": True, "remote_path": virtual, "local_path": str(target), "size": actual, "mtime": downloaded.mtime, "sha256": _sha256(target)}
            return self._run_read(server, action, "下载文件")
        except BaseException:
            _remove_tree_or_raise(target_dir)
            raise

    def upload_file(self, local_path: str, remote_path: str, overwrite: bool = False, alias: str | None = None) -> dict[str, object]:
        server = self.server(alias)
        validate_writable(server)
        virtual = normalize_remote_path(remote_path)
        remote = map_virtual_path(server, virtual)
        local = _validate_local_file(Path(local_path).expanduser())
        _precheck_upload_limit(server, local.stat().st_size)
        def action(driver: Driver, attempt: _WriteAttempt) -> dict[str, object]:
            size = self._upload_one(driver, attempt, server, local, remote, virtual, overwrite)
            return {"ok": True, "remote_path": virtual, "size": size, "status": "completed"}
        return self._run_write(server, action, "上传文件")

    def _upload_one(self, driver: Driver, attempt: _WriteAttempt, server: ServerConfig, local: Path, remote: str, virtual: str, overwrite: bool) -> int:
        _check_remote(driver, remote, server.root, allow_missing_final=True)
        if not overwrite and driver.exists(remote):
            raise AppError("policy_rejected", "目标文件已存在")
        if overwrite and not _supports_atomic_replace(driver):
            raise AppError("policy_rejected", "服务器未确认支持安全原子覆盖")
        temporary = _temporary_path(driver, remote)
        upload_started = False
        try:
            with _open_verified_local(local) as handle:
                attempt.dispatch()
                upload_started = True
                reader = _LimitedReader(handle, server.max_file_size_bytes)
                size = driver.upload(cast(BinaryIO, reader), temporary, True)
            try:
                attempt.dispatch()
                _commit_upload(driver, temporary, remote, overwrite)
            except AppError as exc:
                if exc.error_type == "connection_unavailable":
                    hash_result = self._recover_upload(server, remote, reader.hexdigest)
                    if hash_result == "matched":
                        return size
                    raise _outcome_unknown(
                        "upload_file",
                        [virtual],
                        "postcondition_check",
                        [{"kind": "remote_hash", "result": hash_result, "path": virtual}],
                    ) from exc
                raise
            return size
        except AppError as exc:
            if exc.error_type == "outcome_unknown":
                raise
            if upload_started:
                self._cleanup_temporary(server, temporary)
            raise

    def _cleanup_temporary(self, server: ServerConfig, temporary: str) -> None:
        cleanup: Driver | None = None
        try:
            cleanup = self._driver(server)
            if cleanup.exists(temporary):
                cleanup.delete_file(temporary)
        except Exception as exc:
            raise AppError("server_error", "上传失败且远端临时对象可能残留") from exc
        finally:
            if cleanup is not None:
                cleanup.close()

    def _recover_upload(self, server: ServerConfig, remote: str, expected_hash: str) -> str:
        checker: Driver | None = None
        try:
            checker = self._driver(server)
            remote_hash = _content_hash(checker, remote)
            if remote_hash is None:
                return "unavailable"
            return "matched" if remote_hash == expected_hash else "mismatched"
        except AppError:
            return "check_failed"
        finally:
            if checker is not None:
                checker.close()

    def make_dir(self, path: str, alias: str | None = None) -> dict[str, object]:
        server = self.server(alias)
        validate_writable(server)
        virtual = normalize_remote_path(path)
        _reject_virtual_root(virtual, "创建")
        remote = map_virtual_path(server, virtual)
        def action(driver: Driver, attempt: _WriteAttempt) -> dict[str, object]:
            _check_remote(driver, remote, server.root, allow_missing_final=True)
            existed = driver.exists(remote)
            try:
                attempt.dispatch()
                created = bool(driver.make_dir(remote))
            except AppError as exc:
                if exc.error_type == "connection_unavailable":
                    created = self._recover_make_dir(server, remote, virtual, existed)
                    return {"ok": True, "path": virtual, "created": created, "status": "completed"}
                raise
            return {"ok": True, "path": virtual, "created": created and not existed, "status": "completed"}
        return self._run_write(server, action, "创建目录")

    def _recover_make_dir(self, server: ServerConfig, remote: str, virtual: str, existed: bool) -> bool:
        checker: Driver | None = None
        try:
            checker = self._driver(server)
            _check_remote(checker, remote, server.root, allow_missing_final=True)
            if checker.exists(remote):
                if checker.get_info(remote).type == "dir":
                    return not existed
                raise _outcome_unknown(
                    "make_dir", [virtual], "postcondition_check",
                    [{"kind": "post_state", "result": "mismatched", "path": virtual}],
                )
            try:
                checker.make_dir(remote)
                return True
            except AppError as exc:
                if exc.error_type == "connection_unavailable":
                    raise _outcome_unknown(
                        "make_dir", [virtual], "response_wait",
                        [{"kind": "post_state", "result": "unavailable", "path": virtual}],
                    ) from exc
                raise
        except AppError as exc:
            if exc.error_type == "outcome_unknown":
                raise
            raise _outcome_unknown(
                "make_dir", [virtual], "postcondition_check",
                [{"kind": "post_state", "result": "check_failed", "path": virtual}],
            ) from exc
        finally:
            if checker is not None:
                checker.close()

    def rename(self, path: str, new_name: str, alias: str | None = None) -> dict[str, object]:
        join_remote_child("/", new_name)
        source = normalize_remote_path(path)
        _reject_virtual_root(source, "重命名")
        return self._move_common(source, posixpath.join(posixpath.dirname(source), new_name), alias, "rename")

    def move(self, from_path: str, to_path: str, alias: str | None = None) -> dict[str, object]:
        source, target = normalize_remote_path(from_path), normalize_remote_path(to_path)
        _reject_virtual_root(source, "移动")
        _reject_virtual_root(target, "移动到")
        return self._move_common(source, target, alias, "move")

    def _move_common(self, source_virtual: str, target_virtual: str, alias: str | None, operation: str) -> dict[str, object]:
        server = self.server(alias)
        validate_writable(server)
        source, target = map_virtual_path(server, source_virtual), map_virtual_path(server, target_virtual)
        def action(driver: Driver, attempt: _WriteAttempt) -> dict[str, object]:
            _check_remote(driver, source, server.root)
            _check_remote(driver, target, server.root, allow_missing_final=True)
            info = driver.get_info(source)
            identity = _identity(driver, source)
            if driver.exists(target):
                raise AppError("policy_rejected", "目标已存在")
            try:
                attempt.dispatch()
                driver.move(source, target)
            except AppError as exc:
                if exc.error_type == "connection_unavailable":
                    identity_result = self._recover_move(server, source, target, identity)
                    if identity_result == "matched":
                        keys = ("old_path", "new_path") if operation == "rename" else ("from_path", "to_path")
                        return {"ok": True, keys[0]: source_virtual, keys[1]: target_virtual, "type": _object_type(info.type), "status": "completed"}
                    evidence = [
                        {"kind": "ftp_unique", "result": identity_result, "path": target_virtual},
                    ]
                    raise _outcome_unknown(operation, [source_virtual, target_virtual], "postcondition_check", evidence) from exc
                raise
            keys = ("old_path", "new_path") if operation == "rename" else ("from_path", "to_path")
            return {"ok": True, keys[0]: source_virtual, keys[1]: target_virtual, "type": _object_type(info.type), "status": "completed"}
        return self._run_write(server, action, "移动或重命名")

    def _recover_move(self, server: ServerConfig, source: str, target: str, identity: str | None) -> str:
        if identity is None:
            return "unavailable"
        checker: Driver | None = None
        try:
            checker = self._driver(server)
            if checker.exists(source) or not checker.exists(target):
                return "mismatched"
            checker.get_info(target)
            target_identity = _identity(checker, target)
            if target_identity is None:
                return "unavailable"
            return "matched" if target_identity == identity else "mismatched"
        except AppError:
            return "check_failed"
        finally:
            if checker is not None:
                checker.close()

    def delete(self, path: str, confirm: bool, alias: str | None = None) -> dict[str, object]:
        if confirm is not True:
            raise AppError("policy_rejected", "删除操作未确认")
        server = self.server(alias)
        validate_writable(server)
        virtual = normalize_remote_path(path)
        _reject_virtual_root(virtual, "删除")
        remote = map_virtual_path(server, virtual)
        def action(driver: Driver, attempt: _WriteAttempt) -> dict[str, object]:
            _check_remote(driver, remote, server.root)
            info = driver.get_info(remote)
            identity = _identity(driver, remote)
            if info.type == "dir" and driver.list_dir(remote):
                raise AppError("policy_rejected", "目录非空，拒绝删除")
            try:
                attempt.dispatch()
                driver.delete_dir(remote) if info.type == "dir" else driver.delete_file(remote)
            except AppError as exc:
                if exc.error_type == "connection_unavailable":
                    evidence = self._delete_evidence(server, remote, virtual, identity)
                    raise _outcome_unknown("delete", [virtual], "postcondition_check", evidence) from exc
                raise
            return {"ok": True, "path": virtual, "type": _object_type(info.type), "status": "completed"}
        return self._run_write(server, action, "删除")

    def _delete_evidence(self, server: ServerConfig, remote: str, virtual: str, identity: str | None) -> list[dict[str, str]]:
        checker: Driver | None = None
        evidence: list[dict[str, str]] = []
        try:
            checker = self._driver(server)
            exists = checker.exists(remote)
            evidence.append({"kind": "post_state", "result": "mismatched" if exists else "matched", "path": virtual})
            if identity is not None and exists:
                checker.get_info(remote)
                evidence.append(
                    {
                        "kind": "ftp_unique",
                        "result": "matched" if _identity(checker, remote) == identity else "mismatched",
                        "path": virtual,
                    }
                )
            elif identity is None:
                evidence.append({"kind": "ftp_unique", "result": "unavailable", "path": virtual})
        except AppError:
            evidence.append({"kind": "post_state", "result": "check_failed", "path": virtual})
        finally:
            if checker is not None:
                checker.close()
        return evidence

    def download_dir(self, remote_path: str, alias: str | None = None) -> dict[str, object]:
        server = self.server(alias)
        virtual_root = normalize_remote_path(remote_path)
        remote_root = map_virtual_path(server, virtual_root)
        local_root = self.config.staging_dir / uuid.uuid4().hex / (posixpath.basename(virtual_root.rstrip("/")) or "root")
        def action(driver: Driver) -> dict[str, object]:
            _check_remote(driver, remote_root, server.root)
            if driver.get_info(remote_root).type != "dir":
                raise AppError("policy_rejected", "目标不是目录")
            local_root.mkdir(parents=True, exist_ok=False)
            skipped: list[dict[str, object]] = []
            failed: list[dict[str, object]] = []
            count = total = 0
            def visit(remote_parent: str, virtual_parent: str, local_parent: Path) -> None:
                nonlocal count, total
                for entry in driver.list_dir(remote_parent):
                    try:
                        remote = join_remote_child(remote_parent, entry.name)
                        virtual = join_remote_child(virtual_parent, entry.name)
                        validate_local_component(entry.name)
                        target = local_parent / entry.name
                        if not _within(target, local_root):
                            raise AppError("invalid_path", "下载目录项超出本地 staging 边界")
                    except AppError as exc:
                        failed.append(_batch_failure(virtual_parent, exc))
                        continue
                    if entry.type == "symlink":
                        skipped.append({"path": virtual, "reason_type": "symlink_unsupported", "message": "符号链接不受支持"})
                    elif entry.type == "dir":
                        target.mkdir(parents=True, exist_ok=True)
                        visit(remote, virtual, target)
                    elif entry.type == "file":
                        target.parent.mkdir(parents=True, exist_ok=True)
                        before = FileInfo(remote, "file", entry.size, entry.mtime)
                        try:
                            with target.open("xb") as handle:
                                driver.download(remote, handle)
                            actual = target.stat().st_size
                            if entry.size is not None and actual != entry.size:
                                raise AppError("integrity_check_failed", "下载结果未通过完整性检查")
                            if _source_changed(before, driver.get_info(remote)):
                                raise AppError("integrity_check_failed", "下载期间远端来源发生变化，结果未通过完整性检查")
                            count += 1
                            total += actual
                        except AppError as exc:
                            target.unlink(missing_ok=True)
                            failed.append(_batch_failure(virtual, exc))

            visit(remote_root, virtual_root, local_root)
            return {"ok": True, "remote_path": virtual_root, "local_dir": str(local_root), "file_count": count, "total_size": total, "skipped": skipped, "failed": failed, "status": _batch_status(count, skipped, failed)}
        try:
            return self._run_read(server, action, "下载目录")
        except BaseException:
            if local_root.parent.exists():
                _remove_tree_or_raise(local_root.parent)
            raise

    def upload_dir(self, local_path: str, remote_path: str, overwrite: bool = False, alias: str | None = None) -> dict[str, object]:
        server = self.server(alias)
        validate_writable(server)
        local_root = _validate_local_directory(Path(local_path).expanduser())
        virtual_root = normalize_remote_path(remote_path)
        remote_root = map_virtual_path(server, virtual_root)
        def action(driver: Driver, attempt: _WriteAttempt) -> dict[str, object]:
            active = driver
            replacements: list[Driver] = []

            def reconnect() -> None:
                nonlocal active
                active = self._driver(server)
                replacements.append(active)

            try:
                _check_remote(active, remote_root, server.root, allow_missing_final=True)
                try:
                    attempt.dispatch()
                    active.make_dir(remote_root)
                except AppError as exc:
                    if exc.error_type != "connection_unavailable":
                        raise
                    try:
                        self._recover_make_dir(server, remote_root, virtual_root, False)
                    except AppError as recovery:
                        raise _outcome_unknown("upload_dir", [virtual_root], "postcondition_check", (recovery.details or {}).get("evidence", [])) from exc
                    reconnect()
                skipped: list[dict[str, object]] = []
                failed: list[dict[str, object]] = []
                indeterminate: list[dict[str, object]] = []
                count = total = 0
                for kind, path in _walk_local(local_root):
                    relative = path.relative_to(local_root).as_posix()
                    target = posixpath.join(remote_root, relative)
                    if kind == "symlink":
                        skipped.append({"path": relative, "reason_type": "symlink_unsupported", "message": "符号链接或重解析点不受支持"})
                    elif kind == "dir":
                        try:
                            _check_remote(active, target, server.root, allow_missing_final=True)
                            attempt.dispatch()
                            active.make_dir(target)
                        except AppError as exc:
                            if exc.error_type == "connection_unavailable":
                                try:
                                    self._recover_make_dir(server, target, relative, False)
                                    reconnect()
                                except AppError as recovery:
                                    unknown = _outcome_unknown("upload_dir", [relative], "postcondition_check", (recovery.details or {}).get("evidence", []))
                                    indeterminate.append({"path": relative, "error_type": "outcome_unknown", "message": unknown.message, "evidence": (unknown.details or {}).get("evidence", [])})
                                    reconnect()
                            else:
                                failed.append(_batch_failure(relative, exc))
                    else:
                        try:
                            size = self._upload_one(active, attempt, server, path, target, posixpath.join(virtual_root, relative), overwrite)
                            count += 1
                            total += size
                        except AppError as exc:
                            if exc.error_type == "size_limit_exceeded":
                                skipped.append({"path": relative, "reason_type": "size_limit_exceeded", "message": exc.message, "details": exc.details})
                            elif exc.error_type == "outcome_unknown":
                                indeterminate.append({"path": relative, "error_type": "outcome_unknown", "message": exc.message, "evidence": (exc.details or {}).get("evidence", [])})
                                reconnect()
                            else:
                                failed.append(_batch_failure(relative, exc))
                                if exc.error_type == "connection_unavailable":
                                    reconnect()
                status = "indeterminate" if indeterminate else _batch_status(count, skipped, failed)
                return {"ok": True, "remote_path": virtual_root, "file_count": count, "total_size": total, "skipped": skipped, "failed": failed, "indeterminate": indeterminate, "status": status}
            finally:
                for replacement in replacements:
                    replacement.close()
        return self._run_write(server, action, "上传目录")


def _entry(entry: Entry) -> dict[str, object]:
    return {"name": entry.name, "type": _object_type(entry.type), "size": entry.size, "mtime": entry.mtime}


def _info_result(info: FileInfo, virtual: str) -> dict[str, object]:
    return {"ok": True, "path": virtual, "type": _object_type(info.type), "size": info.size, "mtime": info.mtime}


def _object_type(value: str) -> str:
    return value if value in {"file", "dir", "symlink", "other"} else "other"


def _check_remote(driver: Driver, path: str, root: str, *, allow_missing_final: bool = False) -> None:
    checker = getattr(driver, "check_path", None)
    if checker is not None:
        checker(path, root, allow_missing_final=allow_missing_final)
        return
    try:
        info = driver.get_info(path)
    except AppError as exc:
        if allow_missing_final and exc.error_type == "not_found":
            return
        raise
    if info.type == "symlink":
        raise AppError("symlink_unsupported", "请求路径包含不受支持的符号链接")


def _supports_atomic_replace(driver: Driver) -> bool:
    method = getattr(driver, "supports_atomic_replace", None)
    return bool(method and method())


def _commit_upload(driver: Driver, temporary: str, final: str, overwrite: bool) -> None:
    method = getattr(driver, "commit_upload", None)
    method(temporary, final, overwrite=overwrite) if method else driver.move(temporary, final)


def _identity(driver: Driver, path: str) -> str | None:
    method = getattr(driver, "identity", None)
    return cast(str | None, method(path)) if method is not None else None


def _content_hash(driver: Driver, path: str) -> str | None:
    method = getattr(driver, "content_hash", None)
    return cast(str | None, method(path)) if method is not None else None


def _temporary_path(driver: Driver, final: str) -> str:
    parent, name = posixpath.dirname(final), posixpath.basename(final)
    for _ in range(3):
        candidate = posixpath.join(parent, f".{name}.ft-upload-{secrets.token_hex(8)}.tmp")
        if not driver.exists(candidate):
            return candidate
    raise AppError("server_error", "无法分配上传临时对象")


class _LimitedReader:
    def __init__(self, source: BinaryIO, limit: int) -> None:
        self.source, self.limit, self.observed = source, limit, 0
        self._digest = hashlib.sha256()
    def read(self, size: int = -1) -> bytes:
        request = size
        if self.limit and (size < 0 or size > self.limit + 1 - self.observed):
            request = self.limit + 1 - self.observed
        data = self.source.read(request)
        self.observed += len(data)
        self._digest.update(data)
        if self.limit and self.observed > self.limit:
            raise _limit_error(self.limit, self.observed, "at_least")
        return data

    @property
    def hexdigest(self) -> str:
        return self._digest.hexdigest()


def _precheck_upload_limit(server: ServerConfig, size: int) -> None:
    if server.max_file_size_bytes and size > server.max_file_size_bytes:
        raise _limit_error(server.max_file_size_bytes, size, "exact")


def _limit_error(limit: int, observed: int, observation: str) -> AppError:
    return AppError("size_limit_exceeded", "上传文件超过配置的单文件大小上限", details={"limit_kind": "upload_file_bytes", "configured_limit": limit, "observed_value": observed, "observation": observation, "remote_committed": False})


def _outcome_unknown(
    operation: str,
    paths: list[str],
    phase: str,
    evidence: list[dict[str, str]] | None = None,
) -> AppError:
    return AppError(
        "outcome_unknown",
        "远端写操作的结果无法确认，请人工核验后再决定是否重试",
        details={"operation": operation, "phase": phase, "paths": paths, "evidence": evidence or []},
    )


def _batch_failure(path: str, error: AppError) -> dict[str, object]:
    allowed = {"not_found", "invalid_path", "policy_rejected", "permission_denied", "connection_unavailable", "integrity_check_failed", "server_error"}
    return {"path": path, "error_type": error.error_type if error.error_type in allowed else "server_error", "message": error.message}


def _batch_status(successes: int, skipped: Sequence[object], failed: Sequence[object]) -> str:
    return "complete" if not skipped and not failed else ("partial" if successes else "failed")


def _decode_preview(data: bytes, truncated: bool) -> tuple[str, str, bool]:
    candidates = [("utf-8-sig", "utf-8-sig")] if data.startswith(b"\xef\xbb\xbf") else [("utf-8", "utf-8"), ("gbk", "gbk")]
    for codec, label in candidates:
        candidate = data
        while True:
            try:
                text = candidate.decode(codec)
                partial = truncated and (not text or not text.endswith(("\n", "\r")))
                return text, label, partial
            except UnicodeDecodeError as exc:
                if truncated and exc.end == len(candidate) and candidate:
                    candidate = candidate[:-1]
                    continue
                break
    raise AppError("policy_rejected", "文件无法按 UTF-8 或 GBK 解码")


def _source_changed(before: FileInfo, after: FileInfo) -> bool:
    return (before.size is not None and after.size is not None and before.size != after.size) or (before.mtime is not None and after.mtime is not None and before.mtime != after.mtime)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _is_reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _assert_plain_path(path: Path, *, require_directory: bool = False) -> os.stat_result:
    if not path.is_absolute():
        raise AppError("invalid_path", "本地源路径必须是绝对路径")
    current = Path(path.anchor)
    try:
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
            raise AppError("symlink_unsupported", "本地源路径包含符号链接或重解析点")
        for part in path.parts[1:]:
            current /= part
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                raise AppError("symlink_unsupported", "本地源路径包含符号链接或重解析点")
    except FileNotFoundError as exc:
        raise AppError("not_found", "本地源路径不存在") from exc
    if require_directory and not stat.S_ISDIR(info.st_mode):
        raise AppError("not_found", "本地源路径不是目录")
    if not require_directory and not stat.S_ISREG(info.st_mode):
        raise AppError("not_found", "本地源路径不是普通文件")
    return info


def _validate_local_file(path: Path) -> Path:
    _assert_plain_path(path)
    return path


def _validate_local_directory(path: Path) -> Path:
    _assert_plain_path(path, require_directory=True)
    return path


@contextmanager
def _open_verified_local(path: Path) -> Iterator[BinaryIO]:
    before = _assert_plain_path(path)
    with path.open("rb") as handle:
        after = os.fstat(handle.fileno())
        if not stat.S_ISREG(after.st_mode) or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise AppError("symlink_unsupported", "本地源对象在检查后发生替换")
        yield handle


def _walk_local(root: Path) -> Iterator[tuple[str, Path]]:
    for current, names, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in list(names):
            child = current_path / name
            info = child.lstat()
            if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                names.remove(name)
                yield "symlink", child
            else:
                yield "dir", child
        for name in files:
            child = current_path / name
            info = child.lstat()
            yield ("symlink" if stat.S_ISLNK(info.st_mode) or _is_reparse(info) else "file"), child


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
        return True
    except (OSError, ValueError):
        return False


def _reject_virtual_root(path: str, operation: str) -> None:
    if path == "/":
        raise AppError("policy_rejected", f"禁止对虚拟根目录执行{operation}操作")


def _remove_tree_or_raise(path: Path) -> None:
    if path.exists():
        try:
            shutil.rmtree(path)
        except OSError as exc:
            raise AppError("server_error", "操作失败且本地 staging 中可能存在部分文件") from exc
