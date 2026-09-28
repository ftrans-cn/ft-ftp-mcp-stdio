from __future__ import annotations

import json
from pathlib import Path

import pytest

from ft_ftp_mcp_stdio.config import load_config, load_config_for_discovery
from ft_ftp_mcp_stdio.errors import AppError


def write_config(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def server(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {"alias": "local", "protocol": "ftp", "host": "127.0.0.1", "username": "user", "root": "/data"}
    value.update(changes)
    return value


def test_loads_v2_defaults_and_description(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    write_config(path, {"version": 2, "servers": [server(description="测试服务器")]})
    config = load_config(path, respect_env=False)
    loaded = config.servers["local"]
    assert config.version == 2
    assert loaded.read_only is True
    assert loaded.description == "测试服务器"
    assert loaded.max_file_size_bytes == 2 * 1024**3


@pytest.mark.parametrize("value", [0, 10])
def test_upload_limit_accepts_zero_and_positive(tmp_path: Path, value: int) -> None:
    path = tmp_path / "config.json"
    write_config(path, {"version": 2, "servers": [server(max_file_size_bytes=value)]})
    assert load_config(path, respect_env=False).servers["local"].max_file_size_bytes == value


@pytest.mark.parametrize("value", [-1, True])
def test_upload_limit_rejects_negative_and_boolean(tmp_path: Path, value: object) -> None:
    path = tmp_path / "config.json"
    write_config(path, {"version": 2, "servers": [server(max_file_size_bytes=value)]})
    with pytest.raises(AppError, match="非负整数"):
        load_config(path, respect_env=False)


def test_v1_missing_root_and_removed_batch_fields_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    write_config(path, {"version": 1, "servers": [server()]})
    with pytest.raises(AppError, match="version 必须为 2"):
        load_config(path, respect_env=False)
    write_config(path, {"version": 2, "servers": [{k: v for k, v in server().items() if k != "root"}]})
    with pytest.raises(AppError, match="root"):
        load_config(path, respect_env=False)
    write_config(path, {"version": 2, "servers": [server(max_batch_files=5)]})
    with pytest.raises(AppError, match="未知字段"):
        load_config(path, respect_env=False)


def test_discovery_only_treats_missing_implicit_default_as_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    implicit = tmp_path / "implicit.json"
    monkeypatch.delenv("FT_FTP_MCP_CONFIG", raising=False)
    monkeypatch.setattr("ft_ftp_mcp_stdio.config.default_config_path", lambda: implicit)
    assert load_config_for_discovery() is None
    monkeypatch.setenv("FT_FTP_MCP_CONFIG", str(implicit))
    with pytest.raises(AppError, match="不存在"):
        load_config_for_discovery()


def test_description_length_protocol_fields_and_default_selection(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    write_config(path, {"version": 2, "servers": [server(description="x" * 201)]})
    with pytest.raises(AppError, match="200"):
        load_config(path, respect_env=False)
    write_config(path, {"version": 2, "servers": [server(key_path="key.pem")]})
    with pytest.raises(AppError, match="FTP"):
        load_config(path, respect_env=False)
    write_config(path, {"version": 2, "servers": [server(alias="one"), server(alias="two")]})
    with pytest.raises(AppError, match="default_server"):
        load_config(path, respect_env=False)
