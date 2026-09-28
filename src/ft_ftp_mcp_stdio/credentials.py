from __future__ import annotations

import os

import keyring

from .errors import AppError
from .models import ServerConfig

SERVICE_NAME = "ft-ftp-mcp-stdio"


def _stored_credential(server: ServerConfig) -> tuple[str | None, str | None]:
    try:
        value = keyring.get_password(SERVICE_NAME, server.alias)
    except Exception:  # keyring backends are third-party and may fail independently.  # noqa: BLE001
        value = None
    if value:
        return value, "keyring"
    if server.credential_env:
        value = os.environ.get(server.credential_env)
        if value:
            return value, "env"
        raise AppError(
            "credential_missing",
            f"未找到服务器 {server.alias} 的凭据",
            f"请运行 cred add 或设置环境变量 {server.credential_env}。",
        )
    return None, None


def get_password(server: ServerConfig) -> tuple[str, str]:
    value, source = _stored_credential(server)
    if value and source:
        return value, source
    raise AppError(
        "credential_missing",
        f"未找到服务器 {server.alias} 的凭据",
        f"请运行 cred add {server.alias} 配置凭据。",
    )


def get_optional_passphrase(server: ServerConfig) -> tuple[str | None, str]:
    value, source = _stored_credential(server)
    if value and source:
        return value, source
    return None, "无需（私钥无口令）"
