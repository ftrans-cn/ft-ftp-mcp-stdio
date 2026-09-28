from __future__ import annotations

from dataclasses import replace

import pytest

from ft_ftp_mcp_stdio.errors import AppError
from ft_ftp_mcp_stdio.paths import (
    join_remote_child,
    map_virtual_path,
    normalize_remote_path,
    to_virtual_path,
    validate_local_component,
)


def test_virtual_path_round_trip(ftp_server) -> None:
    server = replace(ftp_server, root="/srv/finance")
    assert map_virtual_path(server, "/") == "/srv/finance"
    assert map_virtual_path(server, "/reports/./a.csv") == "/srv/finance/reports/a.csv"
    assert to_virtual_path(server, "/srv/finance/reports/a.csv") == "/reports/a.csv"


@pytest.mark.parametrize("path", ["", "relative", r"\bad", r"/a\x", "/a\0b", "/a/../b"])
def test_rejects_unsafe_virtual_paths(path: str) -> None:
    with pytest.raises(AppError) as raised:
        normalize_remote_path(path)
    assert raised.value.error_type == "invalid_path"


@pytest.mark.parametrize("name", ["", ".", "..", "a/b", "a\\b", "a\x00b"])
def test_rejects_untrusted_remote_components(name: str) -> None:
    with pytest.raises(AppError):
        join_remote_child("/", name)


@pytest.mark.parametrize("name", ["CON", "aux.txt", "bad:name", "trail.", "trail "])
def test_rejects_windows_unsafe_download_names(name: str) -> None:
    with pytest.raises(AppError) as raised:
        validate_local_component(name)
    assert raised.value.error_type == "invalid_path"


def test_real_path_outside_root_is_never_reflected(ftp_server) -> None:
    server = replace(ftp_server, root="/data")
    with pytest.raises(AppError, match="根目录范围外"):
        to_virtual_path(server, "/database/file")
