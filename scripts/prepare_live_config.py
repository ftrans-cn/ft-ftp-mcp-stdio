"""Create an isolated v2 live-test config without modifying the source config."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def build(
    source: Path,
    destination: Path,
    writable_aliases: set[str],
    root_overrides: dict[str, str],
) -> None:
    if source.resolve() == destination.resolve():
        raise ValueError("source and destination must differ")
    raw = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict) or not isinstance(raw.get("servers"), list):
        raise TypeError("source config is not a supported test fixture")
    servers: list[dict[str, Any]] = []
    allowed = {"alias", "description", "protocol", "host", "port", "username", "root", "encoding", "max_file_size_bytes", "key_path", "credential_env", "host_key_fingerprint"}
    for item in raw["servers"]:
        if not isinstance(item, dict):
            raise TypeError("source server entry is invalid")
        server = {key: value for key, value in item.items() if key in allowed and value is not None}
        alias = server.get("alias")
        if isinstance(alias, str) and alias in root_overrides:
            server["root"] = root_overrides[alias]
        if not isinstance(server.get("root"), str) or not server["root"]:
            raise ValueError(f"server {server.get('alias', '<unknown>')} has no root")
        server["readOnly"] = server.get("alias") not in writable_aliases
        servers.append(server)
    aliases = {server.get("alias") for server in servers}
    missing = writable_aliases - aliases
    if missing:
        raise ValueError(f"writable aliases are missing: {', '.join(sorted(missing))}")
    unknown_overrides = root_overrides.keys() - aliases
    if unknown_overrides:
        raise ValueError(f"root override aliases are missing: {', '.join(sorted(unknown_overrides))}")
    payload = {
        "version": 2,
        "default_server": raw.get("default_server"),
        "staging_dir": str((destination.parent / "staging").resolve()),
        "log_usage": False,
        "servers": servers,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--writable", action="append", default=[])
    parser.add_argument("--root", action="append", default=[], metavar="ALIAS=PATH")
    args = parser.parse_args()
    root_overrides: dict[str, str] = {}
    for value in args.root:
        alias, separator, root = value.partition("=")
        if not separator or not alias or not root:
            parser.error("--root must use ALIAS=PATH")
        if alias in root_overrides:
            parser.error(f"duplicate --root alias: {alias}")
        root_overrides[alias] = root
    build(args.source, args.destination, set(args.writable), root_overrides)


if __name__ == "__main__":
    main()
