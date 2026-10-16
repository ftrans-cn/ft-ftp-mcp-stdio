from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SELECTOR = (
    (ROOT / "install-macos.sh")
    .read_text(encoding="utf-8")
    .split("<<'PY'\n", 1)[1]
    .split("\nPY\n", 1)[0]
)


@pytest.mark.parametrize(
    "architecture,translated", [("arm64", False), ("x86_64", False), ("x86_64", True)]
)
def test_installer_selects_python_architecture(
    architecture: str, translated: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    result = subprocess.CompletedProcess([], 0, "1\n" if translated else "0\n", "")
    with (
        patch.object(platform, "machine", return_value=architecture),
        patch.object(platform, "mac_ver", return_value=("11.0", (), "")),
        patch.object(sys, "version_info", (3, 12, 0)),
        patch.object(subprocess, "run", return_value=result),
    ):
        exec(compile(SELECTOR, "install.sh selector", "exec"), {})  # noqa: S102 - execute the trusted installer selector under mocked platforms.
    captured = capsys.readouterr()
    assert captured.out.strip() == architecture
    assert ("Rosetta" in captured.err) == translated


@pytest.mark.parametrize(
    "architecture,version,macos,message",
    [
        ("i386", (3, 12, 0), "11.0", "Unsupported Python architecture"),
        ("arm64", (3, 13, 0), "11.0", "Python 3.12.x is required"),
        ("x86_64", (3, 12, 0), "10.15", "macOS 11 or later"),
    ],
)
def test_installer_rejects_unsupported_runtime(
    architecture: str, version: tuple[int, int, int], macos: str, message: str
) -> None:
    with (
        patch.object(platform, "machine", return_value=architecture),
        patch.object(platform, "mac_ver", return_value=(macos, (), "")),
        patch.object(sys, "version_info", version),
        pytest.raises(SystemExit, match=message),
    ):
        exec(compile(SELECTOR, "install.sh selector", "exec"), {})  # noqa: S102 - execute the trusted installer selector under mocked platforms.
