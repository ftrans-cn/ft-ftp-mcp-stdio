from __future__ import annotations

import posixpath
import re

from .errors import AppError
from .models import ServerConfig


def normalize_remote_path(path: str) -> str:
    if not isinstance(path, str) or not path:
        raise AppError("invalid_path", "路径不能为空", "请使用服务器端绝对路径（以 / 开头）。")
    if "\\" in path or "\x00" in path or not path.startswith("/"):
        raise AppError("invalid_path", f"非法服务器路径：{path}", "请使用服务器端绝对路径（以 / 开头）。")
    if ".." in path.split("/"):
        raise AppError("invalid_path", f"路径不支持 .. 相对路径段：{path}", "请使用不含 .. 的服务器端绝对路径。")
    normalized = posixpath.normpath(path)
    return "/" if normalized == "." else normalized


def join_remote_child(parent: str, name: str) -> str:
    """Join a server-provided directory entry without trusting its name."""
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
        raise AppError("invalid_path", "服务器返回了非法目录项名称", "请检查服务器目录内容或联系管理员。")
    return posixpath.join(parent, name)


def map_virtual_path(server: ServerConfig, path: str) -> str:
    virtual = normalize_remote_path(path)
    if virtual == "/":
        return server.root
    mapped = posixpath.normpath(posixpath.join(server.root, virtual.lstrip("/")))
    if server.root != "/" and mapped != server.root and not mapped.startswith(server.root + "/"):
        raise AppError("invalid_path", "虚拟路径超出服务器根目录", "请使用服务器虚拟绝对路径。")
    return mapped


def to_virtual_path(server: ServerConfig, path: str) -> str:
    normalized = posixpath.normpath(path)
    if server.root == "/":
        return normalized
    if normalized == server.root:
        return "/"
    if not normalized.startswith(server.root + "/"):
        raise AppError("server_error", "服务器返回了根目录范围外的路径")
    return "/" + normalized[len(server.root) + 1 :]


def validate_path(server: ServerConfig, path: str) -> str:
    """Compatibility name: map a virtual path to its driver path."""
    return map_virtual_path(server, path)


_WINDOWS_RESERVED = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$", re.IGNORECASE)


def validate_local_component(name: str) -> None:
    join_remote_child("/", name)
    if re.match(r"^[A-Za-z]:", name) or name.startswith(("//", "\\\\")):
        raise AppError("invalid_path", "服务器返回了无法安全落盘的目录项")
    if _WINDOWS_RESERVED.match(name) or name[-1:] in {" ", "."} or any(char in name for char in '<>:"|?*'):
        raise AppError("invalid_path", "服务器返回了目标平台不支持的目录项")


def validate_writable(server: ServerConfig) -> None:
    if server.read_only:
        raise AppError("policy_rejected", f"服务器 {server.alias} 配置为只读模式", "请改用可写服务器或关闭 readOnly。")
