from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from ft_ftp_mcp_stdio import setup_wizard as wizard
from ft_ftp_mcp_stdio.config import load_config
from ft_ftp_mcp_stdio.config_store import (
    config_to_dict,
    restore_config,
    save_config_atomic,
)
from ft_ftp_mcp_stdio.errors import AppError
from ft_ftp_mcp_stdio.models import ServerConfig


def test_config_store_round_trip_is_v2_and_omits_removed_limits(app_config, tmp_path: Path) -> None:
    config = replace(app_config, config_path=tmp_path / "config.json")
    original, backup = save_config_atomic(config)
    assert original is None and backup is None
    loaded = load_config(config.config_path, respect_env=False)
    assert loaded == config
    raw = config_to_dict(config)
    assert raw["version"] == 2
    serialized = raw["servers"][0]
    assert "max_batch_files" not in serialized
    assert "max_batch_total_bytes" not in serialized


def test_restore_config_restores_exact_bytes(app_config, tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    original = b'{"old": true}\n'
    path.write_bytes(original)
    restore_config(path, original)
    assert path.read_bytes() == original


def test_new_config_uses_v2_and_safe_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    monkeypatch.setenv("FT_FTP_MCP_CONFIG", str(path))
    server = ServerConfig("new", "ftp", "host", 21, "user", root="/data")
    config = wizard._with_server(None, server)
    assert config.version == 2
    assert config.servers["new"].read_only is True


def test_setup_refuses_existing_v1_without_overwrite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"version": 1, "servers": []}), encoding="utf-8")
    monkeypatch.setenv("FT_FTP_MCP_CONFIG", str(path))
    assert wizard.run_setup(input_fn=lambda prompt: pytest.fail("must stop before prompting")) == 1
    assert "备份" in capsys.readouterr().out
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1


def test_server_validation_requires_root_and_nonnegative_limit() -> None:
    with pytest.raises(AppError, match="root"):
        wizard._validate_server(ServerConfig("x", "ftp", "h", 21, "u", root=""))
    with pytest.raises(AppError, match="非负"):
        wizard._validate_server(ServerConfig("x", "ftp", "h", 21, "u", root="/", max_file_size_bytes=-1))


def test_collected_values_allow_zero_limit_and_reject_invalid_root() -> None:
    wizard._validate_collected_value("max_file", 0)
    with pytest.raises(ValueError):
        wizard._validate_collected_value("root", "/safe/../escape")


def test_client_snippets_use_canonical_registration_name(capsys) -> None:
    wizard.print_client_snippets()
    output = capsys.readouterr().out
    assert '"ft-ftp-mcp-stdio"' in output
    assert "[mcp_servers.ft-ftp-mcp-stdio]" in output


def test_serialization_includes_description(app_config) -> None:
    server = replace(app_config.servers["local"], description="展示名称")
    config = replace(app_config, servers={"local": server})
    assert config_to_dict(config)["servers"][0]["description"] == "展示名称"
