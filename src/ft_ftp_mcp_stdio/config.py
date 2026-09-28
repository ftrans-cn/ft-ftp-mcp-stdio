from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .errors import AppError
from .models import AppConfig, ServerConfig

ALIAS_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def default_config_path() -> Path:
    return Path.home() / ".ft-ftp-mcp" / "config.json"


def _string(data: dict[str, Any], name: str, required: bool = False) -> str | None:
    value = data.get(name)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value:
        raise AppError("invalid_config", f"配置字段 {name} 必须是非空字符串")
    return value


def _int(data: dict[str, Any], name: str, default: int, *, allow_zero: bool = False) -> int:
    value = data.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < (0 if allow_zero else 1):
        expectation = "非负整数" if allow_zero else "正整数"
        raise AppError("invalid_config", f"配置字段 {name} 必须是{expectation}")
    return value


def _port(data: dict[str, Any], default: int) -> int:
    value = _int(data, "port", default)
    if value > 65535:
        raise AppError("invalid_config", "配置字段 port 必须在 1 到 65535 之间")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise AppError("invalid_config", f"配置文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise AppError("invalid_config", f"配置文件 JSON 无法解析（第 {exc.lineno} 行，第 {exc.colno} 列）") from exc
    if not isinstance(data, dict):
        raise AppError("invalid_config", "配置文件顶层必须是 JSON 对象")
    return data


def _root(value: str | None) -> str:
    if value is None:
        raise AppError("invalid_config", "配置字段 root 必须是服务器端绝对路径")
    if not value.startswith("/") or "\\" in value or "//" in value:
        raise AppError("invalid_config", "配置字段 root 必须是服务器端绝对路径")
    stripped = value.rstrip("/") or "/"
    if stripped != "/" and any(part in {".", "..", ""} for part in stripped.split("/")[1:]):
        raise AppError("invalid_config", "配置字段 root 不能包含空段、. 或 ..")
    return stripped


def load_config(path: Path | None = None, *, respect_env: bool = True) -> AppConfig:
    explicit = os.environ.get("FT_FTP_MCP_CONFIG") if respect_env else None
    config_path = Path(explicit).expanduser() if explicit else (path or default_config_path())
    data = _load_json(config_path)
    version = data.get("version")
    if isinstance(version, bool) or version != 2:
        raise AppError("invalid_config", "配置字段 version 必须为 2；请先备份并显式删除或替换旧配置，再重新运行 setup")
    raw_servers = data.get("servers")
    if not isinstance(raw_servers, list) or not raw_servers:
        raise AppError("invalid_config", "配置字段 servers 必须是非空数组")
    servers: dict[str, ServerConfig] = {}
    for raw in raw_servers:
        if not isinstance(raw, dict):
            raise AppError("invalid_config", "servers 中每一项必须是对象")
        server_fields = {"alias", "description", "protocol", "host", "port", "username", "root", "readOnly", "encoding", "max_file_size_bytes", "key_path", "credential_env", "host_key_fingerprint"}
        unknown = set(raw) - server_fields
        if unknown:
            raise AppError("invalid_config", f"服务器配置包含未知字段：{', '.join(sorted(unknown))}")
        alias = _string(raw, "alias", True)
        assert alias is not None
        if not ALIAS_RE.fullmatch(alias) or alias in servers:
            raise AppError("invalid_config", f"服务器别名非法或重复：{alias}")
        protocol = _string(raw, "protocol", True)
        assert protocol is not None
        if protocol not in {"ftp", "sftp"}:
            raise AppError("invalid_config", f"服务器 {alias} 的 protocol 必须是 ftp 或 sftp")
        host = _string(raw, "host", True)
        username = _string(raw, "username", True)
        assert host is not None and username is not None
        description = _string(raw, "description")
        if description is not None and len(description) > 200:
            raise AppError("invalid_config", f"服务器 {alias} 的 description 最长为 200 个字符")
        read_only = raw.get("readOnly", True)
        if not isinstance(read_only, bool):
            raise AppError("invalid_config", f"服务器 {alias} 的 readOnly 必须是布尔值")
        encoding = raw.get("encoding", "auto")
        if encoding not in {"auto", "utf-8", "gbk"}:
            raise AppError("invalid_config", f"服务器 {alias} 的 encoding 不合法")
        key_path_value = _string(raw, "key_path")
        credential_env = _string(raw, "credential_env")
        if credential_env and not ENV_RE.fullmatch(credential_env):
            raise AppError("invalid_config", f"服务器 {alias} 的 credential_env 名称不合法")
        fingerprint = _string(raw, "host_key_fingerprint")
        if protocol == "ftp" and (key_path_value or fingerprint):
            raise AppError("invalid_config", f"FTP 服务器 {alias} 不支持 key_path/host_key_fingerprint")
        if key_path_value and protocol != "sftp":
            raise AppError("invalid_config", f"key_path 仅适用于 SFTP 服务器 {alias}")
        servers[alias] = ServerConfig(
            alias=alias,
            protocol=protocol,
            host=host,
            port=_port(raw, 21 if protocol == "ftp" else 22),
            username=username,
            root=_root(_string(raw, "root")),
            description=description,
            read_only=read_only,
            encoding=encoding,
            max_file_size_bytes=_int(raw, "max_file_size_bytes", 2 * 1024 * 1024 * 1024, allow_zero=True),
            key_path=Path(key_path_value).expanduser() if key_path_value else None,
            credential_env=credential_env,
            host_key_fingerprint=fingerprint,
        )
    default = data.get("default_server")
    if default is None and len(servers) == 1:
        default = next(iter(servers))
    if not isinstance(default, str) or default not in servers:
        raise AppError("invalid_config", "default_server 必须指向 servers 中存在的别名")
    staging_value = data.get("staging_dir", "~/.ft-ftp-mcp/staging")
    if not isinstance(staging_value, str) or not staging_value:
        raise AppError("invalid_config", "staging_dir 必须是非空路径")
    staging_dir = Path(staging_value).expanduser()
    if not staging_dir.is_absolute():
        raise AppError("invalid_config", "staging_dir 必须是本地绝对路径或 ~ 开头路径")
    log_usage = data.get("log_usage", True)
    if not isinstance(log_usage, bool):
        raise AppError("invalid_config", "配置字段 log_usage 必须是布尔值")
    known = {"version", "default_server", "staging_dir", "log_usage", "servers"}
    unknown = set(data) - known
    if unknown:
        raise AppError("invalid_config", f"配置包含未知字段：{', '.join(sorted(unknown))}")
    return AppConfig(2, servers, default, staging_dir, config_path, log_usage)


def load_config_for_discovery(path: Path | None = None) -> AppConfig | None:
    """Return no configuration only for a missing implicit default path."""
    explicit = os.environ.get("FT_FTP_MCP_CONFIG")
    config_path = Path(explicit).expanduser() if explicit else (path or default_config_path())
    if not explicit and not config_path.exists():
        return None
    return load_config(config_path, respect_env=bool(explicit))
