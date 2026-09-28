from __future__ import annotations

from pathlib import Path

import pytest

from ft_ftp_mcp_stdio import usage_log
from ft_ftp_mcp_stdio.models import AppConfig, ServerConfig


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--live", action="store_true", default=False, help="run tests against the configured Serv-U server")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live: requires the explicitly enabled local Serv-U integration environment")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="需要显式传入 --live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def isolated_usage_logs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(usage_log, "usage_log_dir", lambda: tmp_path / "usage-logs")


@pytest.fixture
def ftp_server() -> ServerConfig:
    return ServerConfig("local", "ftp", "127.0.0.1", 21, "zhu", root="/", read_only=False, encoding="gbk")


@pytest.fixture
def app_config(tmp_path: Path, ftp_server: ServerConfig) -> AppConfig:
    return AppConfig(2, {ftp_server.alias: ftp_server}, ftp_server.alias, tmp_path / "staging", tmp_path / "config.json")
