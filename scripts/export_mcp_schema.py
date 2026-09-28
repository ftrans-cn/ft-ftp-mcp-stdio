from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from ft_ftp_mcp_stdio.server import mcp

OUTPUT_PATH = Path(__file__).parents[1] / "docs" / "schema" / "mcp-tools.json"


async def build_snapshot() -> dict[str, Any]:
    tools = await mcp.list_tools()
    return {
        "tools": [
            tool.to_mcp_tool().model_dump(by_alias=True, exclude_none=True)
            for tool in tools
        ]
    }


def main() -> None:
    snapshot = asyncio.run(build_snapshot())
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
