from __future__ import annotations

import posixpath
import re
from collections.abc import Callable
from datetime import UTC, datetime
from ftplib import FTP, Error, all_errors, error_temp
from typing import BinaryIO

from ..errors import AppError, map_exception
from ..models import ServerConfig
from ..paths import join_remote_child
from .base import Entry, FileInfo


def _encoding(value: str) -> str:
    return "utf-8" if value == "auto" else value


_UNIX_LIST_RE = re.compile(
    r"^(?P<mode>[bcdlps-][rwxStTs-]{9})\s+\d+\s+\S+\s+\S+\s+"
    r"(?P<size>\d+)\s+(?P<mtime>\w{3}\s+\d+\s+(?:\d{2}:\d{2}|\d{4}))\s+(?P<name>.+)$"
)


class FTPDriver:
    def __init__(self, server: ServerConfig, password: str, ftp_factory: Callable[[], FTP] = FTP) -> None:
        self.server = server
        self._ftp = ftp_factory()
        self._ftp.encoding = _encoding(server.encoding)
        self._identities: dict[str, str] = {}
        self._missing_prefixes: set[str] = set()
        try:
            self._ftp.connect(server.host, server.port, timeout=30)
            self._ftp.login(server.username, password)
        except Exception as exc:
            self.close()
            raise map_exception(exc, "FTP 登录") from exc

    def banner(self) -> str:
        return self._ftp.getwelcome()[:120]

    def list_dir(self, path: str) -> list[Entry]:
        encodings = ("utf-8", "gbk") if self.server.encoding == "auto" else (_encoding(self.server.encoding),)
        last_error: Exception | None = None
        for encoding in encodings:
            self._ftp.encoding = encoding
            try:
                return self._list_dir_with_fallback(path)
            except UnicodeError as exc:
                last_error = exc
                continue
            except Exception as exc:
                raise map_exception(exc, "列出目录") from exc
        assert last_error is not None
        raise map_exception(last_error, "列出目录") from last_error

    def _list_dir_with_fallback(self, path: str) -> list[Entry]:
        last_error: Exception | None = None
        try:
            entries: list[Entry] = []
            for name, facts in self._ftp.mlsd(path):
                kind = facts.get("type", "file").lower()
                if kind in {"cdir", "pdir"}:
                    continue
                entry_type = "symlink" if "slink" in kind else ("dir" if kind == "dir" else "file")
                entries.append(
                    Entry(
                        name,
                        entry_type,
                        _int(facts.get("size")),
                        _mlsd_time(facts.get("modify")),
                        facts.get("unix.mode"),
                    )
                )
            return entries
        except UnicodeError:
            raise
        except all_errors as exc:
            last_error = exc

        lines: list[str] = []
        try:
            self._ftp.retrlines(f"LIST {path}", lines.append)
            return [_parse_list_line(line) for line in lines if line.strip()]
        except UnicodeError:
            raise
        except all_errors as exc:
            last_error = exc

        try:
            names = self._ftp.nlst(path)
            return [Entry(posixpath.basename(name.rstrip("/")), "file", None, None) for name in names if name.rstrip("/")]
        except UnicodeError:
            raise
        except all_errors as exc:
            last_error = exc

        assert last_error is not None
        raise last_error

    def get_info(self, path: str) -> FileInfo:
        encodings = ("utf-8", "gbk") if self.server.encoding == "auto" else (_encoding(self.server.encoding),)
        last_error: Exception | None = None
        for encoding in encodings:
            self._ftp.encoding = encoding
            try:
                return self._get_info_once(path)
            except UnicodeError as exc:
                last_error = exc
                continue
            except Exception as exc:
                raise map_exception(exc, "获取文件信息") from exc
        assert last_error is not None
        raise map_exception(last_error, "获取文件信息") from last_error

    def identity(self, path: str) -> str | None:
        return self._identities.get(path)

    def _get_info_once(self, path: str) -> FileInfo:
        if path == "/":
            self._ftp.mlsd(path)
            return FileInfo(path, "dir", None, None)
        try:
            facts = dict(self._ftp.mlsd(posixpath.dirname(path) or "/"))
            name = posixpath.basename(path)
            for entry_name, entry_facts in facts.items():
                if entry_name == name:
                    kind = entry_facts.get("type", "file").lower()
                    entry_type = "symlink" if "slink" in kind else ("dir" if kind == "dir" else "file")
                    unique = entry_facts.get("unique")
                    if unique:
                        self._identities[path] = unique
                    return FileInfo(
                        path,
                        entry_type,
                        _int(entry_facts.get("size")),
                        _mlsd_time(entry_facts.get("modify")),
                        entry_facts.get("unix.mode"),
                    )
        except UnicodeError:
            raise
        except all_errors:
            pass
        parent = posixpath.dirname(path) or "/"
        name = posixpath.basename(path)
        for entry in self._list_dir_with_fallback(parent):
            if entry.name == name:
                return FileInfo(path, entry.type, entry.size, entry.mtime, entry.perms)
        size = self._ftp.size(path)
        return FileInfo(path, "file", size, _mdtm(self._ftp, path))

    def download(self, path: str, target: BinaryIO) -> FileInfo:
        info = self.get_info(path)
        if info.type != "file":
            raise AppError("policy_rejected", "目标不是文件", "请使用文件路径。")
        try:
            self._ftp.retrbinary(f"RETR {path}", target.write)
            return info
        except Exception as exc:
            raise map_exception(exc, "下载文件") from exc

    def upload(self, source: BinaryIO, path: str, overwrite: bool) -> int:
        try:
            if not overwrite and self.exists(path):
                raise AppError("policy_rejected", "目标文件已存在", "如需覆盖请确认后显式传 overwrite: true。")
            counted = _CountingReader(source)
            self._ftp.storbinary(f"STOR {path}", counted)
            return counted.bytes_read
        except AppError:
            raise
        except Exception as exc:
            raise map_exception(exc, "上传文件") from exc

    def supports_atomic_replace(self) -> bool:
        # FTP has no portable capability signal for atomic replacement.
        return False

    def commit_upload(self, temporary_path: str, final_path: str, *, overwrite: bool) -> None:
        if overwrite:
            raise AppError("policy_rejected", "服务器未确认支持安全原子覆盖")
        self.move(temporary_path, final_path)

    def check_path(self, path: str, root: str, *, allow_missing_final: bool = False) -> None:
        if allow_missing_final and (path == root or path.startswith(root.rstrip("/") + "/")):
            current = root
            info = self.get_info(current)
            if info.type == "symlink":
                raise AppError("symlink_unsupported", "请求路径包含不受支持的符号链接")
            relative = path[len(root.rstrip("/")):].strip("/")
            for part in relative.split("/") if relative else ():
                entries = self.list_dir(current)
                match = next((entry for entry in entries if entry.name == part), None)
                if match is None:
                    self._missing_prefixes.add(posixpath.join(current.rstrip("/"), part) or "/")
                    return
                if match.type == "symlink":
                    raise AppError("symlink_unsupported", "请求路径包含不受支持的符号链接")
                current = posixpath.join(current.rstrip("/"), part) or "/"
            return
        info = self.get_info(path)
        if info.type == "symlink":
            raise AppError("symlink_unsupported", "请求路径包含不受支持的符号链接")

    def exists(self, path: str) -> bool:
        root = self.server.root.rstrip("/") or "/"
        if path == root:
            return True
        if any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in self._missing_prefixes):
            return False
        if not (path == root or path.startswith(root.rstrip("/") + "/")):
            raise AppError("invalid_path", "远程路径超出配置的服务器根目录")
        current = root
        relative = path[len(root.rstrip("/")):].strip("/")
        for part in relative.split("/") if relative else ():
            match = next((entry for entry in self.list_dir(current) if entry.name == part), None)
            if match is None:
                return False
            current = posixpath.join(current.rstrip("/"), part) or "/"
        return True

    def make_dir(self, path: str) -> list[str]:
        created: list[str] = []
        current = ""
        root = self.server.root.rstrip("/") or "/"
        for part in path.strip("/").split("/"):
            current += "/" + part
            if current == root or root.startswith(current + "/"):
                continue
            try:
                self._ftp.mkd(current)
                created.append(current)
                self._missing_prefixes.clear()
            except all_errors:
                if not self.exists(current):
                    raise AppError("permission_denied", "无法创建远程目录", "请检查服务器权限。")
        return created

    def read_prefix(self, path: str, max_bytes: int) -> bytes:
        data = bytearray()
        connection = None
        try:
            self._ftp.voidcmd("TYPE I")
            connection = self._ftp.transfercmd(f"RETR {path}")
            while len(data) <= max_bytes:
                chunk = connection.recv(min(64 * 1024, max_bytes + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            return bytes(data)
        except Exception as exc:
            raise map_exception(exc, "读取文本预览") from exc
        finally:
            if connection is not None:
                connection.close()
            try:
                self._ftp.voidresp()
            except error_temp:
                pass
            except all_errors:
                pass

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
            self._ftp.rename(from_path, to_path)
        except Exception as exc:
            raise map_exception(exc, "移动或重命名") from exc

    def delete_file(self, path: str) -> None:
        try:
            self._ftp.delete(path)
        except Exception as exc:
            raise map_exception(exc, "删除文件") from exc

    def delete_dir(self, path: str) -> None:
        try:
            self._ftp.rmd(path)
        except Exception as exc:
            raise map_exception(exc, "删除目录") from exc

    def close(self) -> None:
        try:
            self._ftp.quit()
        except all_errors:
            try:
                self._ftp.close()
            except all_errors:
                return


class _CountingReader:
    def __init__(self, source: BinaryIO) -> None:
        self._source = source
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        value = self._source.read(size)
        self.bytes_read += len(value)
        return value


def _parse_list_line(line: str) -> Entry:
    match = _UNIX_LIST_RE.match(line.strip())
    if not match:
        return Entry(line.strip(), "file", None, None)
    mode = match.group("mode")
    name = match.group("name")
    if mode.startswith("l") and " -> " in name:
        name = name.split(" -> ", 1)[0]
    entry_type = "symlink" if mode.startswith("l") else ("dir" if mode.startswith("d") else "file")
    return Entry(
        name,
        entry_type,
        int(match.group("size")),
        None,
        mode,
    )


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _mdtm(ftp: FTP, path: str) -> str | None:
    try:
        response = ftp.sendcmd(f"MDTM {path}")
        stamp = response.split()[-1]
        return datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
    except (Error, OSError, EOFError, ValueError):
        return None


def _mlsd_time(value: str | None) -> str | None:
    if not value:
        return None
    try:
        main, dot, fraction = value.partition(".")
        parsed = datetime.strptime(main, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        if dot:
            parsed = parsed.replace(microsecond=int((fraction + "000000")[:6]))
        return parsed.isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError):
        return None
