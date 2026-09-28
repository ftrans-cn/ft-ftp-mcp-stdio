from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServerConfig:
    alias: str
    protocol: str
    host: str
    port: int
    username: str
    root: str
    description: str | None = None
    read_only: bool = True
    encoding: str = "auto"
    max_file_size_bytes: int = 2 * 1024 * 1024 * 1024
    key_path: Path | None = None
    credential_env: str | None = None
    host_key_fingerprint: str | None = None


@dataclass(frozen=True)
class AppConfig:
    version: int
    servers: dict[str, ServerConfig]
    default_server: str | None
    staging_dir: Path
    config_path: Path
    log_usage: bool = True
