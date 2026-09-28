from __future__ import annotations

import base64
import hashlib
import stat
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, cast

import paramiko

from ..errors import AppError, map_exception
from ..known_hosts import KnownHostsStore
from ..models import ServerConfig
from ..paths import join_remote_child
from .base import Entry, FileInfo


class SFTPDriver:
    def __init__(
        self,
        server: ServerConfig,
        password: str,
        known_hosts: Path,
        client_factory: Callable[[], paramiko.SSHClient] = paramiko.SSHClient,
        write_known_hosts: bool = True,
    ) -> None:
        self.server = server
        self._client = client_factory()
        self._sftp: paramiko.SFTPClient | None = None
        try:
            self._client.set_missing_host_key_policy(
                _VerifyingHostKeyPolicy(server, KnownHostsStore(known_hosts), write_known_hosts)
            )
            if server.key_path:
                self._client.connect(
                    hostname=server.host,
                    port=server.port,
                    username=server.username,
                    timeout=30,
                    auth_timeout=30,
                    banner_timeout=30,
                    key_filename=str(server.key_path),
                    passphrase=password or None,
                )
            else:
                self._client.connect(
                    hostname=server.host,
                    port=server.port,
                    username=server.username,
                    timeout=30,
                    auth_timeout=30,
                    banner_timeout=30,
                    password=password,
                )
            self._sftp = self._client.open_sftp()
        except AppError:
            self.close()
            raise
        except Exception as exc:
            self.close()
            raise map_exception(exc, "SFTP 登录") from exc

    def _verify_host_key(self, known_hosts: Path, write_known_hosts: bool = True) -> None:
        transport = self._client.get_transport()
        if transport is None:
            raise AppError("connection_unavailable", "SFTP 传输层未建立")
        key = transport.get_remote_server_key()
        fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")
        expected = self.server.host_key_fingerprint
        KnownHostsStore(known_hosts).verify(
            self.server.alias,
            key.get_name(),
            fingerprint,
            expected,
            persist=write_known_hosts,
        )

    def banner(self) -> str:
        transport = self._client.get_transport()
        return transport.remote_version if transport else "SFTP"

    def list_dir(self, path: str) -> list[Entry]:
        try:
            result = []
            for item in self._require_sftp().listdir_attr(path):
                mode = cast(int, item.st_mode)
                kind = "symlink" if stat.S_ISLNK(mode) else ("dir" if stat.S_ISDIR(mode) else "file")
                result.append(Entry(item.filename, kind, item.st_size if kind == "file" else None, _mtime(item.st_mtime), oct(mode & 0o777)))
            return result
        except Exception as exc:
            raise map_exception(exc, "列出目录") from exc

    def get_info(self, path: str) -> FileInfo:
        try:
            item = self._require_sftp().lstat(path)
            mode = cast(int, item.st_mode)
            kind = "symlink" if stat.S_ISLNK(mode) else ("dir" if stat.S_ISDIR(mode) else "file")
            return FileInfo(path, kind, item.st_size if kind == "file" else None, _mtime(item.st_mtime), oct(mode & 0o777))
        except Exception as exc:
            raise map_exception(exc, "获取文件信息") from exc

    def supports_atomic_replace(self) -> bool:
        # Paramiko exposes posix_rename even when the server extension is absent,
        # so method presence is not a reliable capability signal.
        return False

    def commit_upload(self, temporary_path: str, final_path: str, *, overwrite: bool) -> None:
        try:
            if overwrite:
                self._require_sftp().posix_rename(temporary_path, final_path)
            else:
                self._require_sftp().rename(temporary_path, final_path)
        except Exception as exc:
            raise map_exception(exc, "提交上传") from exc

    def check_path(self, path: str, root: str, *, allow_missing_final: bool = False) -> None:
        root_parts = [part for part in root.split("/") if part]
        path_parts = [part for part in path.split("/") if part]
        current = ""
        for index, part in enumerate(path_parts):
            current += "/" + part
            try:
                item = self._require_sftp().lstat(current)
            except FileNotFoundError as exc:
                if allow_missing_final and index >= len(root_parts):
                    return
                raise AppError("not_found", "请求的远程对象不存在") from exc
            except PermissionError as exc:
                raise AppError("permission_denied", "服务器拒绝检查请求路径") from exc
            except (OSError, paramiko.SSHException) as exc:
                raise map_exception(exc, "检查远程路径") from exc
            if stat.S_ISLNK(cast(int, item.st_mode)):
                in_root = index < len(root_parts)
                raise AppError(
                    "invalid_config" if in_root else "symlink_unsupported",
                    "配置的服务器根目录包含符号链接" if in_root else "请求路径包含不受支持的符号链接",
                )

    def download(self, path: str, target: BinaryIO) -> FileInfo:
        info = self.get_info(path)
        if info.type != "file":
            raise AppError("policy_rejected", "目标不是文件", "请使用文件路径。")
        try:
            with self._require_sftp().open(path, "rb") as source:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
            return info
        except Exception as exc:
            raise map_exception(exc, "下载文件") from exc

    def upload(self, source: BinaryIO, path: str, overwrite: bool) -> int:
        if not overwrite and self.exists(path):
            raise AppError("policy_rejected", "目标文件已存在", "如需覆盖请确认后显式传 overwrite: true。")
        try:
            size = 0
            with self._require_sftp().open(path, "wb") as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
                    size += len(chunk)
            return size
        except AppError:
            raise
        except Exception as exc:
            raise map_exception(exc, "上传文件") from exc

    def exists(self, path: str) -> bool:
        try:
            self._require_sftp().lstat(path)
            return True
        except Exception as exc:
            mapped = map_exception(exc, "检查远程对象")
            if mapped.error_type == "not_found":
                return False
            raise mapped from exc

    def make_dir(self, path: str) -> list[str]:
        created: list[str] = []
        current = ""
        for part in path.strip("/").split("/"):
            current += "/" + part
            try:
                item = self._require_sftp().lstat(current)
                mode = cast(int, item.st_mode)
                if stat.S_ISLNK(mode):
                    root = self.server.root.rstrip("/") or "/"
                    in_root = current == root or root.startswith(current + "/")
                    raise AppError(
                        "invalid_config" if in_root else "symlink_unsupported",
                        "配置的服务器根目录包含符号链接" if in_root else "请求路径包含不受支持的符号链接",
                    )
                if not stat.S_ISDIR(mode):
                    raise AppError("policy_rejected", "远程路径段不是目录")
            except AppError:
                raise
            except Exception as exc:
                mapped = map_exception(exc, "检查远程目录")
                if mapped.error_type != "not_found":
                    raise mapped from exc
                try:
                    self._require_sftp().mkdir(current)
                    created.append(current)
                except Exception as mkdir_exc:
                    raise map_exception(mkdir_exc, "创建目录") from mkdir_exc
        return created

    def read_prefix(self, path: str, max_bytes: int) -> bytes:
        try:
            with self._require_sftp().open(path, "rb") as source:
                return source.read(max_bytes + 1)
        except Exception as exc:
            raise map_exception(exc, "读取文本预览") from exc

    def walk(self, path: str) -> list[FileInfo]:
        result: list[FileInfo] = []

        def visit(current: str) -> None:
            for entry in self.list_dir(current):
                child = join_remote_child(current, entry.name)
                result.append(FileInfo(child, entry.type, entry.size, entry.mtime, entry.perms))
                if entry.type == "dir":
                    visit(child)

        visit(path)
        return result

    def move(self, from_path: str, to_path: str) -> None:
        try:
            self._require_sftp().rename(from_path, to_path)
        except Exception as exc:
            raise map_exception(exc, "移动或重命名") from exc

    def delete_file(self, path: str) -> None:
        try:
            self._require_sftp().remove(path)
        except Exception as exc:
            raise map_exception(exc, "删除文件") from exc

    def delete_dir(self, path: str) -> None:
        try:
            self._require_sftp().rmdir(path)
        except Exception as exc:
            raise map_exception(exc, "删除目录") from exc

    def close(self) -> None:
        if self._sftp is not None:
            try:
                self._sftp.close()
            except (OSError, paramiko.SSHException):
                return
        try:
            self._client.close()
        except (OSError, paramiko.SSHException):
            return

    def _require_sftp(self) -> paramiko.SFTPClient:
        if self._sftp is None:
            raise AppError("connection_unavailable", "SFTP 连接未建立")
        return self._sftp


def _mtime(value: int | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return None


class _VerifyingHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    def __init__(self, server: ServerConfig, store: KnownHostsStore, persist: bool) -> None:
        self.server = server
        self.store = store
        self.persist = persist

    def missing_host_key(self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey) -> None:
        del client, hostname
        fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip("=")
        self.store.verify(
            self.server.alias,
            key.get_name(),
            fingerprint,
            self.server.host_key_fingerprint,
            persist=self.persist,
        )
