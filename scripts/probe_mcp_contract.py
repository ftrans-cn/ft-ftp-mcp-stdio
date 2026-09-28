from __future__ import annotations

import asyncio
import json
from importlib.metadata import version
from typing import Literal

from fastmcp import Client, FastMCP
from fastmcp.tools import ToolResult
from mcp.types import ToolAnnotations

OUTPUT_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "type": "object",
            "properties": {
                "ok": {"const": True},
                "mode": {"const": "ok"},
            },
            "required": ["ok", "mode"],
            "additionalProperties": False,
        },
        {
            "type": "object",
            "properties": {
                "ok": {"const": False},
                "error_type": {"const": "probe_error"},
            },
            "required": ["ok", "error_type"],
            "additionalProperties": False,
        },
    ],
}


async def probe() -> dict[str, object]:
    server = FastMCP("contract-capability-probe")
    calls = 0

    @server.tool(
        title="Contract probe",
        output_schema=OUTPUT_SCHEMA,
        annotations=ToolAnnotations(
            title="Read-only contract probe",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    def success_probe(mode: Literal["ok"]) -> ToolResult:
        nonlocal calls
        calls += 1
        return ToolResult(structured_content={"ok": True, "mode": mode})

    @server.tool(output_schema=OUTPUT_SCHEMA)
    def runtime_error_probe() -> ToolResult:
        return ToolResult(
            structured_content={"ok": False, "error_type": "probe_error"},
            is_error=True,
        )

    async with Client(server) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
        listed = tools["success_probe"]
        assert listed.output_schema is not None
        assert listed.output_schema.get("type") == "object"
        assert "oneOf" in listed.output_schema
        assert listed.title == "Contract probe"
        assert listed.annotations is not None
        assert listed.annotations.title == "Read-only contract probe"
        assert listed.annotations.read_only_hint is True
        assert listed.annotations.destructive_hint is False
        assert listed.annotations.idempotent_hint is True
        assert listed.annotations.open_world_hint is False

        success = await client.call_tool("success_probe", {"mode": "ok"})
        assert success.is_error is False
        assert success.structured_content == {"ok": True, "mode": "ok"}

        runtime_error = await client.call_tool(
            "runtime_error_probe", raise_on_error=False
        )
        assert runtime_error.is_error is True
        assert runtime_error.structured_content == {
            "ok": False,
            "error_type": "probe_error",
        }

        bad_enum = await client.call_tool(
            "success_probe", {"mode": "invalid"}, raise_on_error=False
        )
        assert bad_enum.is_error is True
        assert bad_enum.structured_content is None
        assert calls == 1

        missing_argument = await client.call_tool(
            "success_probe", {}, raise_on_error=False
        )
        assert missing_argument.is_error is True
        assert missing_argument.structured_content is None
        assert calls == 1

    return {
        "versions": {
            "fastmcp": version("fastmcp"),
            "mcp": version("mcp"),
            "mcp-types": version("mcp-types"),
        },
        "checks": {
            "root_object_with_one_of": "passed",
            "runtime_error_structured_content": "passed",
            "tool_title_and_annotations": "passed",
            "enum_rejected_before_tool_body": "passed",
            "framework_argument_error_has_null_structured_content": "passed",
        },
    }


def main() -> None:
    print(json.dumps(asyncio.run(probe()), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
