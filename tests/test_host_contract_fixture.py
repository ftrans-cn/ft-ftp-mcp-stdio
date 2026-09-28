from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType

import jsonschema  # type: ignore[import-untyped]
from fastmcp import Client

from ft_ftp_mcp_stdio import server
from ft_ftp_mcp_stdio.contracts import OUTPUT_SCHEMAS


def _load_fixture() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "host_contract_fixture.py"
    spec = importlib.util.spec_from_file_location("host_contract_fixture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_host_contract_fixture_returns_valid_indeterminate_result() -> None:
    result = _load_fixture().upload_dir_result()
    jsonschema.Draft202012Validator(OUTPUT_SCHEMAS["upload_dir"]).validate(result)
    assert result["status"] == "indeterminate"
    assert result["indeterminate"] == [
        {
            "path": "uncertain.txt",
            "error_type": "outcome_unknown",
            "message": "远端写操作的结果无法确认，请人工核验后再决定是否重试",
            "evidence": [{"kind": "post_state", "result": "check_failed", "path": "uncertain.txt"}],
        }
    ]


def test_host_contract_fixture_uses_real_tool_metadata_and_wire_result(monkeypatch) -> None:
    module = _load_fixture()
    monkeypatch.setattr(server, "_service", lambda config=None: module.FixtureService())
    monkeypatch.setattr(server, "record_usage", lambda *args, **kwargs: None)

    async def run() -> None:
        async with Client(server.mcp) as client:
            tools = await client.list_tools()
            upload_dir = next(tool for tool in tools if tool.name == "upload_dir")
            assert upload_dir.annotations is not None
            assert upload_dir.annotations.destructive_hint is True
            assert upload_dir.annotations.idempotent_hint is False
            assert "不得整体重试" in (upload_dir.description or "")
            result = await client.call_tool(
                "upload_dir",
                {"local_path": "C:/fixture", "remote_path": "/fixture"},
                raise_on_error=False,
            )
            assert result.is_error is False
            assert result.structured_content is not None
            assert result.structured_content["status"] == "indeterminate"

    asyncio.run(run())
