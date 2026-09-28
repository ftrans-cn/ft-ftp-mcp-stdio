from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import load_config
from .models import AppConfig, ServerConfig


def config_to_dict(config: AppConfig) -> dict[str, Any]:
    return {
        "version": config.version,
        "default_server": config.default_server,
        "staging_dir": str(config.staging_dir),
        "log_usage": config.log_usage,
        "servers": [_server_to_dict(server) for server in config.servers.values()],
    }


def _server_to_dict(server: ServerConfig) -> dict[str, Any]:
    result: dict[str, Any] = {
        "alias": server.alias,
        "protocol": server.protocol,
        "host": server.host,
        "port": server.port,
        "username": server.username,
        "root": server.root,
        "readOnly": server.read_only,
        "encoding": server.encoding,
        "max_file_size_bytes": server.max_file_size_bytes,
    }
    if server.description is not None:
        result["description"] = server.description
    if server.key_path is not None:
        result["key_path"] = str(server.key_path)
    if server.credential_env is not None:
        result["credential_env"] = server.credential_env
    if server.host_key_fingerprint is not None:
        result["host_key_fingerprint"] = server.host_key_fingerprint
    return result


def save_config_atomic(config: AppConfig) -> tuple[bytes | None, Path | None]:
    path = config.config_path
    original = path.read_bytes() if path.exists() else None
    backup = None
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config_to_dict(config), ensure_ascii=False, indent=2) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        load_config(temporary, respect_env=False)
        if original is not None:
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
            backup = path.with_name(f"{path.name}.bak.{stamp}")
            backup.write_bytes(original)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return original, backup


def restore_config(path: Path, original: bytes | None) -> None:
    if original is None:
        path.unlink(missing_ok=True)
        return
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".restore", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(original)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
