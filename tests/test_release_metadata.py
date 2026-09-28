from __future__ import annotations

import tomllib
from pathlib import Path

from ft_ftp_mcp_stdio import __version__
from ft_ftp_mcp_stdio.server import mcp

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_consistent() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = metadata["project"]["version"]

    assert version == __version__ == mcp.version
    for relative in (
        "README.md",
        "docs/spec/current.md",
        "docs/architecture.md",
        "docs/schema/config.schema.json",
        "docs/用户手册_v1.12.md",
        "docs/产品能力清单_v0.4.md",
    ):
        assert version in (ROOT / relative).read_text(encoding="utf-8"), relative


def test_offline_build_uses_dynamic_version_and_manifest() -> None:
    wheel_script = (ROOT / "scripts/build_offline_wheels.ps1").read_text(encoding="utf-8")
    package_script = (ROOT / "scripts/build_offline_package.ps1").read_text(encoding="utf-8")
    installer = (ROOT / "install.bat").read_text(encoding="utf-8")

    assert "pyproject.toml" in wheel_script
    assert "wheelhouse-manifest.json" in wheel_script
    assert "pyproject.toml" in package_script
    assert "wheelhouse-manifest.json" in package_script
    assert "VERSION.txt" in package_script
    assert "VERSION.txt" in installer
    assert "ft-ftp-mcp-stdio==%PACKAGE_VERSION%" in installer
    assert "0.2.2" not in wheel_script
    assert "0.2.2" not in package_script
    assert "0.2.2" not in installer
