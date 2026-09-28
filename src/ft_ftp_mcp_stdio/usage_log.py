from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import load_config
from .errors import AppError

LOGGER = logging.getLogger(__name__)
PATH_ARGUMENTS = {"path", "remote_path", "local_path", "from_path", "to_path"}
_warning_lock = threading.Lock()
_warning_emitted = False


def usage_log_dir() -> Path:
    return Path.home() / ".ft-ftp-mcp" / "logs"


def record_usage(
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    elapsed_seconds: float,
) -> None:
    try:
        try:
            config = load_config()
        except AppError:
            config = None
        if config is not None and not config.log_usage:
            return
        alias = arguments.get("server") or (config.default_server if config is not None else None)
        paths = {name: value for name, value in arguments.items() if name in PATH_ARGUMENTS and isinstance(value, str)}
        timestamp = datetime.now(UTC)
        event = {
            "timestamp": timestamp.isoformat(),
            "tool": tool_name,
            "server": alias,
            "paths": paths,
            "status": "success" if result.get("ok") is True else str(result.get("error_type", "error")),
            "duration_ms": round(elapsed_seconds * 1000, 3),
        }
        directory = usage_log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"usage-{timestamp.astimezone():%Y%m%d}.jsonl"
        with target.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:  # Usage logging is explicitly best-effort.  # noqa: BLE001
        _warn_once()


def _warn_once() -> None:
    global _warning_emitted
    with _warning_lock:
        if _warning_emitted:
            return
        _warning_emitted = True
    LOGGER.warning("使用日志写入失败；工具调用将继续执行，本进程不再重复提示。")
