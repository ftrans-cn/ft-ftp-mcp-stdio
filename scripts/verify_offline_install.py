from __future__ import annotations

import asyncio
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

EXPECTED_TOOLS = {
    "delete",
    "download_dir",
    "download_file",
    "get_file_info",
    "list_dir",
    "list_servers",
    "make_dir",
    "move",
    "read_text_preview",
    "rename",
    "search_files",
    "test_connection",
    "upload_dir",
    "upload_file",
}


async def verify(expected_version: str) -> None:
    installed_version = version("ft-ftp-mcp-stdio")
    if installed_version != expected_version:
        raise RuntimeError(f"installed version {installed_version} != {expected_version}")

    runtime_dir = Path(sys.executable).resolve().parent
    config = runtime_dir / ".release-verification-missing-config.json"
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "ft_ftp_mcp_stdio"],
        env={
            **os.environ,
            "FASTMCP_SHOW_SERVER_BANNER": "false",
            "FT_FTP_MCP_CONFIG": str(config),
            "PYTHONUTF8": "1",
        },
        cwd=str(runtime_dir),
    )
    async with Client(transport) as client:
        server_version = client.server_info.version
        tools = {tool.name for tool in await client.list_tools()}

    if server_version != expected_version:
        raise RuntimeError(f"MCP version {server_version} != {expected_version}")
    if tools != EXPECTED_TOOLS:
        raise RuntimeError(f"unexpected tools: {sorted(tools)}")
    print(json.dumps({"version": installed_version, "tool_count": len(tools), "stdio": "passed"}))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_offline_install.py <expected-version>")
    asyncio.run(verify(sys.argv[1]))
