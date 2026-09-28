from __future__ import annotations

import asyncio
import json
from pathlib import Path

import jsonschema  # type: ignore[import-untyped]
from fastmcp import Client

from ft_ftp_mcp_stdio.contracts import ERROR_TYPES
from ft_ftp_mcp_stdio.server import mcp

ROOT = Path(__file__).parents[1]
TOOLS = {"list_servers", "test_connection", "list_dir", "search_files", "get_file_info", "read_text_preview", "download_file", "upload_file", "make_dir", "rename", "move", "delete", "download_dir", "upload_dir"}


def runtime_document() -> dict[str, object]:
    tools = asyncio.run(mcp.list_tools())
    return {"tools": [tool.to_mcp_tool().model_dump(by_alias=True, exclude_none=True) for tool in tools]}


def test_formal_mcp_schema_matches_runtime_tools_list() -> None:
    expected = json.loads((ROOT / "docs/schema/mcp-tools.json").read_text(encoding="utf-8"))
    assert expected == runtime_document()


def test_all_tools_have_closed_contracts_titles_descriptions_and_annotations() -> None:
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == TOOLS
    for tool in tools:
        listed = tool.to_mcp_tool()
        assert listed.title and listed.description
        assert listed.annotations is not None
        assert listed.input_schema["additionalProperties"] is False
        assert listed.output_schema is not None
        assert listed.output_schema["type"] == "object"
        assert "oneOf" in listed.output_schema
        for variant in listed.output_schema["oneOf"]:
            assert variant["additionalProperties"] is False


def test_error_union_contains_exactly_thirteen_variants() -> None:
    tool = next(tool.to_mcp_tool() for tool in asyncio.run(mcp.list_tools()) if tool.name == "list_servers")
    assert tool.output_schema is not None
    variants = tool.output_schema["oneOf"][1:]
    assert {variant["properties"]["error_type"]["const"] for variant in variants} == set(ERROR_TYPES)


def test_example_config_matches_v2_json_schema() -> None:
    schema = json.loads((ROOT / "docs/schema/config.schema.json").read_text(encoding="utf-8"))
    example = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(example, schema)
    assert example["version"] == 2


def test_framework_and_runtime_errors_remain_distinct(monkeypatch) -> None:
    from ft_ftp_mcp_stdio import server
    from ft_ftp_mcp_stdio.errors import AppError

    monkeypatch.setattr(server, "_service", lambda config=None: type("S", (), {"delete": lambda self, path, confirm, alias: (_ for _ in ()).throw(AppError("policy_rejected", "confirmation required"))})())

    async def run() -> None:
        async with Client(mcp) as client:
            runtime = await client.call_tool("delete", {"path": "/x", "confirm": False}, raise_on_error=False)
            assert runtime.is_error is True
            assert runtime.structured_content["error_type"] == "policy_rejected"
            missing = await client.call_tool("delete", {"path": "/x"}, raise_on_error=False)
            assert missing.is_error is True
            assert missing.structured_content is None
    asyncio.run(run())
