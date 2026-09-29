from __future__ import annotations

import getpass
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import keyring

from .config import ALIAS_RE, default_config_path, load_config
from .config_store import restore_config, save_config_atomic
from .credentials import SERVICE_NAME, get_optional_passphrase, get_password
from .drivers.ftp import FTPDriver
from .drivers.sftp import SFTPDriver
from .errors import AppError
from .models import AppConfig, ServerConfig

Input = Callable[[str], str]
SecretInput = Callable[[str], str]


def run_setup(input_fn: Input = input, secret_fn: SecretInput = getpass.getpass) -> int:
    while True:
        try:
            config = _load_optional_config()
        except AppError as exc:
            print(f"失败：{exc.message}")
            return 1
        print("\nFT Agent FTP 配置向导")
        print("1. 添加服务器  2. 修改服务器  3. 删除服务器")
        print("4. 切换默认服务器  5. 检测客户端并打印配置片段  6. 设置使用日志")
        print("7. 列出服务器  0. 退出")
        choice = input_fn("请选择: ").strip()
        try:
            if choice == "1":
                _upsert(config, None, input_fn, secret_fn)
            elif choice == "2":
                _upsert(config, _choose_alias(config, input_fn), input_fn, secret_fn)
            elif choice == "3":
                _remove(config, _choose_alias(config, input_fn), input_fn)
            elif choice == "4":
                _set_default(config, _choose_alias(config, input_fn))
            elif choice == "5":
                print_client_snippets()
            elif choice == "6":
                _set_log_usage(config, input_fn)
            elif choice == "7":
                _list_servers(config)
            elif choice == "0":
                return 0
            else:
                print("无效选择，请重试。")
        except _Cancelled:
            print("已返回主菜单，配置未改变。")
        except KeyboardInterrupt:
            print("\n已中断，配置未改变。")
            return 130
        except AppError as exc:
            print(f"失败：{exc.message}")
            if exc.hint:
                print(f"建议：{exc.hint}")


class _Cancelled(Exception):
    pass


def _load_optional_config() -> AppConfig | None:
    try:
        return load_config()
    except AppError as exc:
        if "配置文件不存在" not in exc.message:
            raise
        return None


def _choose_alias(config: AppConfig | None, input_fn: Input) -> str:
    if config is None or not config.servers:
        raise AppError("not_found", "当前没有已配置服务器")
    print("可用服务器：" + ", ".join(config.servers))
    alias = input_fn("服务器别名（b 返回）: ").strip()
    if alias.lower() == "b":
        raise _Cancelled
    if alias not in config.servers:
        raise AppError("not_found", f"服务器 {alias} 未在配置中定义")
    return alias


def _upsert(config: AppConfig | None, editing: str | None, input_fn: Input, secret_fn: SecretInput) -> None:
    current = config.servers[editing] if config is not None and editing else None
    values = _collect_server_values(current, editing, input_fn, secret_fn)
    alias = editing or str(values["alias"])
    if not ALIAS_RE.fullmatch(alias):
        raise AppError("invalid_config", "服务器别名格式不合法")
    if editing is None and config is not None and alias in config.servers:
        raise AppError("invalid_config", f"服务器别名重复：{alias}")
    protocol = str(values["protocol"])
    root = str(values["root"])
    key_value = str(values["key_path"])
    key_path = Path(key_value).expanduser() if key_value else None
    server = ServerConfig(
        alias,
        protocol,
        str(values["host"]),
        int(values["port"]),
        str(values["username"]),
        root=root.rstrip("/") or "/",
        description=str(values["description"]) or None,
        read_only=bool(values["read_only"]),
        encoding=str(values["encoding"]),
        max_file_size_bytes=int(values["max_file"]),
        key_path=key_path,
        credential_env=None,
        host_key_fingerprint=str(values["fingerprint"]) or None,
    )
    _validate_server(server)
    supplied = values["secret"]
    assert supplied is None or isinstance(supplied, str)
    credential = _credential_for_test(server, supplied, current is not None)
    config_path = config.config_path if config else _new_config_path()
    _test_candidate(server, credential, config_path.parent / "known_hosts")
    updated = _with_server(config, server)
    original, backup = save_config_atomic(updated)
    try:
        if supplied is not None:
            if supplied:
                keyring.set_password(SERVICE_NAME, alias, supplied)
            elif server.key_path and current is None:
                pass
            elif not server.key_path and current is None:
                raise AppError("credential_missing", "密码不能为空")
    except KeyboardInterrupt:
        restore_config(updated.config_path, original)
        raise
    except Exception as exc:
        restore_config(updated.config_path, original)
        raise AppError("server_error", "凭据写入失败，配置已回滚", "检查操作系统钥匙串后重试。") from exc
    print(f"服务器 {alias} 已保存并通过连接测试。")
    if backup:
        print(f"原配置备份：{backup}")


def _collect_server_values(
    current: ServerConfig | None,
    editing: str | None,
    input_fn: Input,
    secret_fn: SecretInput,
) -> dict[str, Any]:
    fields: list[tuple[str, str, object, str]] = []
    if editing is None:
        fields.append(("alias", "别名（1-64 位，支持中英文、数字、点、短横线和下划线）", "", "text"))
    fields.extend(
        [
            ("protocol", "协议 ftp/sftp", current.protocol if current else "ftp", "choice:ftp,sftp"),
            ("host", "服务器地址", current.host if current else "", "text"),
            ("port", "端口", current.port if current else 0, "int"),
            ("username", "用户名", current.username if current else "", "text"),
            ("root", "root（必填，/ 表示服务器根）", current.root if current else "/", "text"),
            ("description", "说明（可选，最长 200 字符）", current.description if current else "", "optional"),
            ("read_only", "readOnly y/n", "n" if current and not current.read_only else "y", "bool"),
            ("encoding", "文件名编码 auto/utf-8/gbk", current.encoding if current else "auto", "choice:auto,utf-8,gbk"),
            ("max_file", "单文件上限（字节）", current.max_file_size_bytes if current else 2 * 1024**3, "int"),
            ("key_path", "私钥路径（留空使用密码）", str(current.key_path) if current and current.key_path else "", "optional"),
            ("fingerprint", "主机指纹（留空使用 TOFU）", current.host_key_fingerprint if current else "", "optional"),
            ("secret", "密码或私钥口令（修改时留空保留现值）", "", "secret"),
        ]
    )
    values: dict[str, Any] = {}
    index = 0

    def skipped(position: int) -> bool:
        name = fields[position][0]
        return name in {"key_path", "fingerprint"} and values.get("protocol") == "ftp"

    while index < len(fields):
        name, label, default, kind = fields[index]
        if skipped(index):
            values[name] = None if name == "secret" else ""
            index += 1
            continue
        if name == "port" and not default:
            default = 21 if values.get("protocol") == "ftp" else 22
        suffix = f" [{default}]" if default not in {None, ""} else ""
        prompt = f"{label}{suffix}（b 返回上一步）: "
        raw = secret_fn(prompt) if kind == "secret" else input_fn(prompt).strip()
        if raw.lower() == "b":
            if index == 0:
                raise _Cancelled
            index -= 1
            while index > 0 and skipped(index):
                index -= 1
            continue
        raw = raw or str(default or "")
        try:
            if kind == "int":
                parsed: Any = int(raw)
                if (name == "port" and not 1 <= parsed <= 65535) or (name == "max_file" and parsed < 0):
                    raise ValueError
            elif kind == "bool":
                if raw.lower() not in {"y", "n"}:
                    raise ValueError
                parsed = raw.lower() == "y"
            elif kind.startswith("choice:"):
                choices = set(kind.split(":", 1)[1].split(","))
                parsed = raw.lower()
                if parsed not in choices:
                    raise ValueError
            else:
                parsed = raw
                if kind == "text" and not parsed:
                    raise ValueError
            _validate_collected_value(name, parsed)
        except ValueError:
            print(f"{label} 输入不合法，请重试。")
            continue
        values[name] = parsed
        index += 1
    return values


def _credential_for_test(server: ServerConfig, supplied: str | None, editing: bool) -> str:
    if server.credential_env:
        value = os.environ.get(server.credential_env)
        if not value:
            raise AppError("credential_missing", f"环境变量 {server.credential_env} 未设置")
        return value
    if supplied:
        return supplied
    if editing:
        try:
            value, _ = get_optional_passphrase(server) if server.key_path else get_password(server)
            return value or ""
        except AppError:
            if not server.key_path:
                raise
    if server.key_path:
        return ""
    raise AppError("credential_missing", "密码不能为空")


def _test_candidate(server: ServerConfig, credential: str, known_hosts: Path) -> None:
    driver = FTPDriver(server, credential) if server.protocol == "ftp" else SFTPDriver(server, credential, known_hosts)
    try:
        driver.banner()
    finally:
        driver.close()


def _with_server(config: AppConfig | None, server: ServerConfig) -> AppConfig:
    if config is None:
        path = _new_config_path()
        return AppConfig(2, {server.alias: server}, server.alias, path.parent / "staging", path)
    servers = dict(config.servers)
    servers[server.alias] = server
    return replace(config, servers=servers)


def _new_config_path() -> Path:
    explicit = os.environ.get("FT_FTP_MCP_CONFIG")
    return Path(explicit).expanduser() if explicit else default_config_path()


def _remove(config: AppConfig | None, alias: str, input_fn: Input) -> None:
    assert config is not None
    servers = dict(config.servers)
    if len(servers) == 1:
        raise AppError("policy_rejected", "不能删除唯一的服务器配置")
    if alias == config.default_server and len(servers) > 2:
        raise AppError("policy_rejected", "删除默认服务器前必须先显式切换默认服务器")
    del servers[alias]
    default = config.default_server
    if alias == default:
        default = next(iter(servers))
        print(f"默认服务器已自动切换为 {default}。")
    remove_credential = _bool(input_fn, f"是否同时删除 {alias} 的钥匙串凭据（默认保留）", False)
    updated = replace(config, servers=servers, default_server=default)
    original, backup = save_config_atomic(updated)
    try:
        if remove_credential:
            try:
                keyring.delete_password(SERVICE_NAME, alias)
            except keyring.errors.PasswordDeleteError:
                pass
    except KeyboardInterrupt:
        restore_config(updated.config_path, original)
        raise
    except Exception as exc:
        restore_config(updated.config_path, original)
        raise AppError("server_error", "凭据删除失败，配置已回滚", "检查操作系统钥匙串后重试。") from exc
    print(f"服务器 {alias} 已删除；钥匙串凭据{'已删除' if remove_credential else '已保留'}。")
    if backup:
        print(f"原配置备份：{backup}")


def _set_default(config: AppConfig | None, alias: str) -> None:
    assert config is not None
    updated = replace(config, default_server=alias)
    _, backup = save_config_atomic(updated)
    print(f"默认服务器已切换为 {alias}。")
    if backup:
        print(f"原配置备份：{backup}")


def _set_log_usage(config: AppConfig | None, input_fn: Input) -> None:
    if config is None:
        raise AppError("not_found", "请先添加服务器配置")
    enabled = _bool(input_fn, "是否启用 JSONL 使用日志", config.log_usage)
    updated = replace(config, log_usage=enabled)
    _, backup = save_config_atomic(updated)
    print(f"使用日志已{'开启' if enabled else '关闭'}。")
    if backup:
        print(f"原配置备份：{backup}")


def _list_servers(config: AppConfig | None) -> None:
    if config is None or not config.servers:
        print("当前没有已配置服务器")
        return
    print("别名 | 协议 | 地址:端口 | 用户名 | root | readOnly | 凭据方式 | 默认")
    print("--- | --- | --- | --- | --- | --- | --- | ---")
    for server in config.servers.values():
        if server.credential_env:
            credential = "环境变量"
        elif server.key_path:
            credential = "SFTP 私钥"
        else:
            credential = "钥匙串密码"
        default = "是" if server.alias == config.default_server else ""
        print(
            f"{server.alias} | {server.protocol} | {server.host}:{server.port} | {server.username} | "
            f"{server.root or '/'} | {'是' if server.read_only else '否'} | {credential} | {default}"
        )


def print_client_snippets() -> None:
    home = Path.home()
    candidates = {
        "Claude Desktop": home / "AppData/Roaming/Claude/claude_desktop_config.json",
        "Codex": home / ".codex/config.toml",
        "WorkBuddy": home / ".workbuddy/mcp.json",
    }
    detected = [name for name, path in candidates.items() if path.exists()]
    print("检测到的客户端：" + (", ".join(detected) if detected else "未检测到（仍可手动配置）"))
    command = sys.executable
    args = [] if getattr(sys, "frozen", False) else ["-m", "ft_ftp_mcp_stdio"]
    environment = {"FASTMCP_SHOW_SERVER_BANNER": "false", "PYTHONUTF8": "1"}
    snippet = {"mcpServers": {"ft-ftp-mcp-stdio": {"command": command, "args": args, "env": environment}}}
    print(json.dumps(snippet, ensure_ascii=False, indent=2))
    print("Codex TOML：")
    toml_args = "[]" if not args else '["-m", "ft_ftp_mcp_stdio"]'
    print(
        f'[mcp_servers.ft-ftp-mcp-stdio]\ncommand = "{command.replace(chr(92), "/")}"\nargs = {toml_args}\n\n'
        '[mcp_servers.ft-ftp-mcp-stdio.env]\nFASTMCP_SHOW_SERVER_BANNER = "false"\nPYTHONUTF8 = "1"'
    )


def _validate_collected_value(name: str, value: object) -> None:
    if name == "alias" and (not isinstance(value, str) or not ALIAS_RE.fullmatch(value)):
        raise ValueError
    if name == "root" and (
        not isinstance(value, str)
        or not value.startswith("/")
        or "\\" in value
        or "//" in value
        or any(part in {".", ".."} for part in value.split("/"))
    ):
        raise ValueError
    if name == "description" and isinstance(value, str) and len(value) > 200:
        raise ValueError


def _validate_server(server: ServerConfig) -> None:
    if not 1 <= server.port <= 65535:
        raise AppError("invalid_config", "端口必须在 1 到 65535 之间")
    if not server.root or not server.root.startswith("/") or "\\" in server.root or "//" in server.root:
        raise AppError("invalid_config", "root 必须是规范的服务器绝对路径")
    if server.root and any(part in {".", ".."} for part in server.root.split("/")):
        raise AppError("invalid_config", "root 不能包含 . 或 .. 路径段")
    if server.description is not None and (not server.description or len(server.description) > 200):
        raise AppError("invalid_config", "description 必须是最长 200 字符的非空字符串")
    if server.max_file_size_bytes < 0:
        raise AppError("invalid_config", "单文件上传上限必须是非负整数")
    if server.protocol == "ftp" and (server.key_path or server.host_key_fingerprint):
        raise AppError("invalid_config", "FTP 不支持私钥或主机指纹字段")
    if server.credential_env and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", server.credential_env):
        raise AppError("invalid_config", "凭据环境变量名不合法")


def _value(input_fn: Input, label: str, default: str | None, required: bool = False) -> str:
    suffix = f" [{default}]" if default not in {None, ""} else ""
    value = input_fn(f"{label}{suffix}（b 返回）: ").strip()
    if value.lower() == "b":
        raise _Cancelled
    value = value or (default or "")
    if required and not value:
        raise AppError("invalid_config", f"{label}不能为空")
    return value


def _bool(input_fn: Input, label: str, default: bool) -> bool:
    raw = _value(input_fn, f"{label} y/n", "y" if default else "n", required=True).lower()
    if raw not in {"y", "n"}:
        raise AppError("invalid_config", f"{label} 只能输入 y 或 n")
    return raw == "y"
