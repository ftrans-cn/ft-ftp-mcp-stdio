"""Cross-build locked macOS offline ZIPs; does not execute macOS binaries.

Run with Python 3.12 containing pip and packaging, and uv on PATH.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from collections import deque
from email.parser import BytesParser
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import compatible_tags, cpython_tags, mac_platforms
from packaging.utils import canonicalize_name, parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> str:
    result = subprocess.run(args, cwd=ROOT, check=False, text=True, capture_output=True)
    if result.returncode:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        result.check_returncode()
    return result.stdout


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def locked_requirements(text: str, environment: dict[str, str]) -> dict[str, str]:
    selected: dict[str, str] = {}
    for block in text.replace("\\\n", " ").splitlines():
        line = block.strip()
        if not line or line.startswith("#"):
            continue
        requirement_text, hashes = line.split(" --hash=", 1)
        requirement = Requirement(requirement_text.strip())
        if requirement.marker is None or requirement.marker.evaluate(environment):
            requirement.marker = None
            selected[canonicalize_name(requirement.name)] = (
                f"{requirement} --hash={hashes}"
            )
    return selected


def build(arch: str) -> tuple[dict[str, bytes], bytes, dict[str, object]]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    version = project["version"]
    environment = {key: str(value) for key, value in default_environment().items()}
    environment.update(
        sys_platform="darwin",
        os_name="posix",
        platform_system="Darwin",
        platform_machine=arch,
        python_version="3.12",
        python_full_version="3.12.0",
        implementation_name="cpython",
        platform_python_implementation="CPython",
        implementation_version="3.12.0",
        platform_release="20.0.0",
        platform_version="",
        extra="",
    )
    # Evaluate markers explicitly: pip download otherwise uses Windows markers.
    exported = run("uv", "export", "--locked", "--no-dev", "--no-emit-project")
    selected = locked_requirements(exported, environment)
    override = ROOT / "scripts" / "requirements-macos-x86_64.txt"
    if arch == "x86_64":
        overrides = locked_requirements(
            override.read_text(encoding="utf-8"), environment
        )
        if set(overrides) != {"cryptography"}:
            raise RuntimeError(
                "Intel compatibility lock must only override cryptography"
            )
        selected.update(overrides)
    platforms = list(mac_platforms(version=(11, 0), arch=arch))
    supported = set(cpython_tags((3, 12), platforms=platforms))
    supported.update(compatible_tags((3, 12), interpreter="cp312", platforms=platforms))
    build_root = ROOT / "build" / "macos"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{arch}-", dir=build_root) as temporary:
        stage = Path(temporary)
        wheels = stage / "wheels"
        wheels.mkdir()
        requirements = stage / "download.txt"
        requirements.write_text("\n".join(selected.values()) + "\n", encoding="utf-8")
        print(f"Downloading locked macOS {arch} dependencies...", flush=True)
        command = [
            sys.executable,
            "-m",
            "pip",
            "--isolated",
            "download",
            "--no-deps",
            "--require-hashes",
            "--only-binary=:all:",
            "--python-version",
            "3.12",
            "--implementation",
            "cp",
            "--abi",
            "cp312",
            "--dest",
            str(wheels),
            "-r",
            str(requirements),
        ]
        for platform in platforms:
            command.extend(["--platform", platform])
        run(*command)
        run(
            "uv",
            "build",
            "--wheel",
            "--out-dir",
            str(wheels),
            "--python",
            sys.executable,
            "--no-create-gitignore",
        )
        metadata = {}
        name: str
        pinned = []
        for wheel in sorted(wheels.glob("*.whl")):
            name, wheel_version, _, tags = parse_wheel_filename(wheel.name)
            if not tags.intersection(supported):
                raise RuntimeError(f"Incompatible wheel: {wheel.name}")
            if name in metadata:
                raise RuntimeError(f"Duplicate distribution: {name}")
            with zipfile.ZipFile(wheel) as archive:
                entry = next(
                    n for n in archive.namelist() if n.endswith(".dist-info/METADATA")
                )
                metadata[name] = BytesParser().parsebytes(archive.read(entry))
            pinned.append(
                f"{name}=={wheel_version} --hash=sha256:{digest(wheel.read_bytes())}"
            )
        # Check the entire active dependency closure, including requested extras.
        queue = deque([Requirement(f"ft-ftp-mcp-stdio=={version}")])
        visited = set()
        while queue:
            requirement = queue.popleft()
            name = canonicalize_name(requirement.name)
            key = (name, tuple(sorted(requirement.extras)))
            if name not in metadata:
                raise RuntimeError(f"Missing dependency: {requirement}")
            package = metadata[name]
            if package["Version"] not in requirement.specifier:
                raise RuntimeError(f"Version mismatch: {requirement}")
            if key in visited:
                continue
            visited.add(key)
            for dependency in package.get_all("Requires-Dist", []):
                child = Requirement(dependency)
                if child.marker is None or any(
                    child.marker.evaluate({**environment, "extra": extra})
                    for extra in {"", *requirement.extras}
                ):
                    queue.append(child)
        return (
            {p.name: p.read_bytes() for p in wheels.glob("*.whl")},
            ("\n".join(pinned) + "\n").encode(),
            {
                "wheel_count": len(metadata),
                "dependency_closure": "verified",
                "dependency_overrides": {"cryptography": "48.0.1"}
                if arch == "x86_64"
                else {},
                "compatibility_lock_sha256": digest(override.read_bytes())
                if arch == "x86_64"
                else None,
            },
        )


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Build with Python 3.12.x")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    release = ROOT / "release" / version
    release.mkdir(parents=True, exist_ok=True)
    output = release / f"ft-ftp-mcp-stdio-offline-{version}-py312-macos.zip"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing artifact: {output}")
    arm, arm_requirements, arm_info = build("arm64")
    intel, intel_requirements, intel_info = build("x86_64")
    common = arm.keys() & intel.keys()
    for name in common:
        if arm[name] != intel[name]:
            raise RuntimeError(f"Same wheel filename has different contents: {name}")
    files = {f"wheels/common/{name}": arm[name] for name in common}
    for arch, wheels in (("arm64", arm), ("x86_64", intel)):
        files.update(
            {
                f"wheels/{arch}/{name}": data
                for name, data in wheels.items()
                if name not in common
            }
        )
    manual_name = f"FTP-MCP-快速安装手册-macOS-v{version}.md"
    files.update(
        {
            "install.sh": (ROOT / "install-macos.sh")
            .read_text(encoding="utf-8")
            .encode(),
            "VERSION.txt": f"{version}\n".encode(),
            "requirements-arm64.txt": arm_requirements,
            "requirements-x86_64.txt": intel_requirements,
            "compatibility-lock-x86_64.txt": (
                ROOT / "scripts/requirements-macos-x86_64.txt"
            ).read_bytes(),
            manual_name: (ROOT / "docs" / manual_name).read_bytes(),
            "LICENSE": (ROOT / "LICENSE").read_bytes(),
        }
    )
    for name in ("codex-config.toml", "workbuddy-mcp.json"):
        files[f"templates/{name}.template"] = (
            ROOT / "templates" / f"{name}.template"
        ).read_bytes()
    files["BUILD-INFO.json"] = (
        json.dumps(
            {
                "version": version,
                "architectures": {"arm64": arm_info, "x86_64": intel_info},
                "minimum_macos": "11.0",
                "python": "3.12",
                "native_macos_execution": "not performed",
                "source_commit": run("git", "rev-parse", "HEAD").strip(),
                "source_has_changes": bool(run("git", "status", "--porcelain").strip()),
                "lock_sha256": digest((ROOT / "uv.lock").read_bytes()),
                "builder_sha256": digest(Path(__file__).read_bytes()),
                "common_wheel_count": len(common),
                "unique_wheel_count": len(arm) + len(intel) - len(common),
            },
            indent=2,
        )
        + "\n"
    ).encode()
    build_root = ROOT / "build" / "macos"
    with tempfile.TemporaryDirectory(prefix="universal-", dir=build_root) as temporary:
        stage = Path(temporary)
        files["SHA256SUMS.txt"] = "".join(
            f"{digest(data)}  {name}\n" for name, data in sorted(files.items())
        ).encode()
        candidate = stage / "package.zip"
        with zipfile.ZipFile(candidate, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = (
                    0o100755 if name == "install.sh" else 0o100644
                ) << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(candidate) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == set(files)
            for name, data in files.items():
                assert archive.read(name) == data
        candidate.replace(output)
        checksum = digest(output.read_bytes())
        output.with_suffix(".zip.sha256").write_text(
            f"{checksum}  {output.name}\n", encoding="utf-8"
        )
        print(
            f"MACOS_PACKAGE_OK architectures=arm64,x86_64 common_wheels={len(common)} unique_wheels={len(arm) + len(intel) - len(common)} sha256={checksum} path={output}",
            flush=True,
        )


if __name__ == "__main__":
    main()
