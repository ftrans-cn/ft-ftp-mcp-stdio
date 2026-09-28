from __future__ import annotations

import importlib.metadata
import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import load_config
from .credentials import get_optional_passphrase, get_password
from .drivers.base import Driver
from .drivers.ftp import FTPDriver
from .drivers.sftp import SFTPDriver
from .errors import AppError
from .known_hosts import KnownHostsStore
from .models import AppConfig, ServerConfig
from .service import FileService
from .usage_log import usage_log_dir


@dataclass(frozen=True)
class Check:
    status: str
    name: str
    conclusion: str
    suggestion: str = ""


def run_doctor(server_alias: str | None = None) -> int:
    checks = diagnose(server_alias)
    for check in checks:
        line = f"{check.status:<4} {check.name}: {check.conclusion}"
        if check.suggestion:
            line += f"；建议：{check.suggestion}"
        print(line)
    return 1 if any(check.status == "FAIL" for check in checks) else 0


def diagnose(server_alias: str | None = None) -> list[Check]:
    checks = [_runtime_check(), _log_directory_check()]
    try:
        config = load_config()
        checks.append(Check("PASS", "配置文件", f"解析成功：{config.config_path}"))
    except AppError as exc:
        checks.append(Check("FAIL", "配置文件", exc.message, exc.hint or "修复 config.json 后重试"))
        checks.append(Check("SKIP", "服务器检查", "配置不可用，已跳过凭据、网络和协议检查"))
        return checks
    aliases = [server_alias] if server_alias else list(config.servers)
    if server_alias and server_alias not in config.servers:
        checks.append(Check("FAIL", "服务器选择", f"别名 {server_alias} 不存在", "检查 --server 参数"))
        return checks
    for alias in aliases:
        server = config.servers[alias]
        checks.extend(_server_checks(config, server))
    return checks


def _log_directory_check() -> Check:
    directory = usage_log_dir()
    candidate = directory
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    if candidate.is_dir() and os.access(candidate, os.W_OK):
        detail = str(directory) if directory.exists() else f"{directory}（可由现有父目录创建）"
        return Check("PASS", "使用日志目录", f"可写：{detail}")
    return Check("FAIL", "使用日志目录", f"不可写：{directory}", "检查目录 ACL 或用户主目录权限")


def _runtime_check() -> Check:
    if sys.version_info[:2] != (3, 12):
        return Check("FAIL", "运行环境", f"Python {sys.version.split()[0]} 不受支持", "仅支持 Python 3.12.x")
    versions = []
    for package in ("fastmcp", "keyring", "paramiko"):
        try:
            versions.append(f"{package}={importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            return Check("FAIL", "运行环境", f"缺少依赖 {package}", "重新安装本程序及依赖")
    return Check("PASS", "运行环境", f"Python {sys.version.split()[0]}；" + "，".join(versions))


def _server_checks(config: AppConfig, server: ServerConfig) -> list[Check]:
    checks: list[Check] = []
    if server.root == "/":
        checks.append(Check("WARN", f"{server.alias}/root", "root 为 /，隔离依赖服务端 chroot、虚拟根或受限账号"))
    if server.description and _description_may_be_sensitive(server.description):
        checks.append(Check("WARN", f"{server.alias}/description", "说明文字可能包含连接、账号或本机路径信息", "仅保留用于选择服务器的非敏感说明"))
    try:
        _, source = get_optional_passphrase(server) if server.protocol == "sftp" and server.key_path else get_password(server)
        checks.append(Check("PASS", f"{server.alias}/凭据", f"可用（来源：{source}）"))
    except AppError as exc:
        checks.append(Check("FAIL", f"{server.alias}/凭据", exc.message, exc.hint))
    try:
        with socket.create_connection((server.host, server.port), timeout=5):
            pass
        checks.append(Check("PASS", f"{server.alias}/TCP", f"{server.host}:{server.port} 可达"))
    except OSError:
        checks.append(Check("FAIL", f"{server.alias}/TCP", f"{server.host}:{server.port} 不可达", "检查地址、端口、防火墙和服务器状态"))
    service = FileService(config, lambda candidate, password: _diagnostic_driver(candidate, password, config.config_path.parent / "known_hosts"))
    login_ok = False
    try:
        result = service.test_connection(server.alias)
        login_ok = True
        checks.append(Check("PASS", f"{server.alias}/协议登录", f"{result['protocol']} 登录成功"))
    except AppError as exc:
        checks.append(Check("FAIL", f"{server.alias}/协议登录", exc.message, exc.hint))
    if server.protocol == "ftp":
        try:
            service.list_dir("/", server.alias)
            checks.append(Check("PASS", f"{server.alias}/FTP数据通道", "被动模式目录列表成功"))
        except AppError as exc:
            checks.append(
                Check(
                    "FAIL",
                    f"{server.alias}/FTP数据通道",
                    exc.message,
                    "检查服务器被动端口范围、防火墙和 NAT 配置",
                )
            )
    else:
        checks.append(_fingerprint_check(config.config_path.parent / "known_hosts", server, login_ok))
    return checks


def _diagnostic_driver(server: ServerConfig, password: str, known_hosts: Path) -> Driver:
    if server.protocol == "ftp":
        return FTPDriver(server, password)
    return SFTPDriver(server, password, known_hosts, write_known_hosts=False)


def _fingerprint_check(known_hosts: Path, server: ServerConfig, verified: bool) -> Check:
    if server.host_key_fingerprint:
        status = "PASS" if verified else "WARN"
        conclusion = "已配置固定主机指纹，登录时校验通过" if verified else "已配置固定主机指纹，但登录失败，未能核验"
        return Check(status, f"{server.alias}/SFTP指纹", conclusion, "先修复协议登录问题" if not verified else "")
    try:
        known = KnownHostsStore(known_hosts).inspect()
    except AppError as exc:
        return Check("WARN", f"{server.alias}/SFTP指纹", exc.message, "检查文件权限和格式")
    if server.alias in known:
        status = "PASS" if verified else "WARN"
        conclusion = "已有 TOFU 指纹，登录时校验通过" if verified else "已有 TOFU 指纹，但登录失败，未能核验"
        return Check(status, f"{server.alias}/SFTP指纹", conclusion, "先修复协议登录问题" if not verified else "")
    return Check("WARN", f"{server.alias}/SFTP指纹", "尚无已信任指纹；doctor 未写入 known_hosts", "通过正常 MCP 连接建立 TOFU 记录")


def _description_may_be_sensitive(value: str) -> bool:
    lowered = value.lower()
    return any(marker in value for marker in ("/", "\\", "@", ":")) or any(
        marker in lowered for marker in ("id_rsa", "id_ed25519", ".pem", ".ppk")
    )
