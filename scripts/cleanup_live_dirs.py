"""Delete explicitly named live-test directories through the guarded delete service."""

from __future__ import annotations

import argparse
from typing import Any

from ft_ftp_mcp_stdio.config import load_config
from ft_ftp_mcp_stdio.errors import AppError
from ft_ftp_mcp_stdio.service import FileService


def delete_tree(service: FileService, path: str, alias: str) -> bool:
    try:
        entries = service.list_dir(path, alias)["entries"]
    except AppError:
        return False
    assert isinstance(entries, list)
    for raw_entry in entries:
        entry = raw_entry
        assert isinstance(entry, dict)
        child = f"{path.rstrip('/')}/{entry['name']}"
        if entry["type"] == "dir":
            delete_tree(service, child, alias)
        else:
            service.delete(child, True, alias)
    service.delete(path, True, alias)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args(argv)
    if not args.confirm:
        parser.error("deletion requires --confirm")
    if any(not path.startswith("/mcp_") or ".." in path.split("/") for path in args.paths):
        parser.error("only absolute /mcp_* test paths without '..' are accepted")
    service = FileService(load_config())
    results: dict[str, Any] = {path: "deleted" if delete_tree(service, path, args.server) else "not_found" for path in args.paths}
    print(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
