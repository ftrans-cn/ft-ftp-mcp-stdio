from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from ft_ftp_mcp_stdio import server as mcp_server
from ft_ftp_mcp_stdio import usage_log
from ft_ftp_mcp_stdio.config_store import save_config_atomic
from ft_ftp_mcp_stdio.errors import AppError


def test_usage_log_contains_only_required_fields(monkeypatch, app_config, tmp_path: Path) -> None:
    config = replace(app_config, config_path=tmp_path / "config.json", log_usage=True)
    save_config_atomic(config)
    monkeypatch.setenv("FT_FTP_MCP_CONFIG", str(config.config_path))
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(usage_log, "usage_log_dir", lambda: log_dir)

    secret_content = "TOP-SECRET-FILE-CONTENT"
    credential = "TOP-SECRET-PASSWORD"
    usage_log.record_usage(
        "upload_file",
        {
            "local_path": "D:/data/report.csv",
            "remote_path": "/root/report.csv",
            "server": "local",
            "overwrite": False,
            "credential": credential,
            "content": secret_content,
        },
        {"ok": True, "content": secret_content},
        0.01234,
    )

    log_file = next(log_dir.glob("usage-*.jsonl"))
    assert log_file.name == f"usage-{datetime.now(UTC).astimezone():%Y%m%d}.jsonl"
    raw = log_file.read_text(encoding="utf-8")
    event = json.loads(raw)
    assert set(event) == {"timestamp", "tool", "server", "paths", "status", "duration_ms"}
    assert event["tool"] == "upload_file"
    assert event["server"] == "local"
    assert event["paths"] == {"local_path": "D:/data/report.csv", "remote_path": "/root/report.csv"}
    assert event["status"] == "success"
    assert event["duration_ms"] == 12.34
    assert credential not in raw
    assert secret_content not in raw


def test_usage_log_can_be_disabled(monkeypatch, app_config, tmp_path: Path) -> None:
    config = replace(app_config, config_path=tmp_path / "config.json", log_usage=False)
    save_config_atomic(config)
    monkeypatch.setenv("FT_FTP_MCP_CONFIG", str(config.config_path))
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(usage_log, "usage_log_dir", lambda: log_dir)

    usage_log.record_usage("list_dir", {"path": "/root"}, {"ok": False, "error_type": "not_found"}, 0.001)

    assert not log_dir.exists()


def test_usage_log_failure_warns_once_and_does_not_raise(monkeypatch, caplog, tmp_path: Path) -> None:
    blocked = tmp_path / "file"
    blocked.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(usage_log, "usage_log_dir", lambda: blocked / "logs")
    monkeypatch.setattr(usage_log, "load_config", lambda: (_ for _ in ()).throw(AppError("invalid_config", "test")))
    monkeypatch.setattr(usage_log, "_warning_emitted", False)
    caplog.set_level(logging.WARNING)

    usage_log.record_usage("list_dir", {"path": "/"}, {"ok": True}, 0.0)
    usage_log.record_usage("list_dir", {"path": "/"}, {"ok": True}, 0.0)

    assert sum("使用日志写入失败" in record.message for record in caplog.records) == 1


def test_safe_tool_records_each_server_invocation_once(monkeypatch) -> None:
    events: list[tuple[str, dict[str, object], dict[str, object], float]] = []
    monkeypatch.setattr(mcp_server, "record_usage", lambda *event: events.append(event))

    @mcp_server._safe_tool
    def sample_tool(path: str, server: str | None = None) -> dict[str, object]:
        return {"ok": True, "path": path, "server": server}

    result = sample_tool("/report.txt", "ftp1").structured_content
    assert result is not None
    assert result["ok"] is True
    assert len(events) == 1
    assert events[0][0] == "sample_tool"
    assert events[0][1] == {"path": "/report.txt", "server": "ftp1"}
