import re
from pathlib import Path

import pytest

from app.agent.tools.policy import execute_tool
from app.mcp.client import InProcessMCPClient
from app.mcp.server import build_mcp_server, get_mcp_server


@pytest.fixture
def mcp(tmp_path: Path) -> InProcessMCPClient:
    return InProcessMCPClient(build_mcp_server(notes_path=tmp_path / "notes.jsonl"))


async def test_mcp_lists_allowlisted_tools(mcp: InProcessMCPClient) -> None:
    names = await mcp.list_remote_tools()
    assert names == ["calculator", "clock", "save_note"]


async def test_mcp_calculator_through_client(mcp: InProcessMCPClient) -> None:
    assert await mcp.call_tool("calculator", {"expression": "12 * (3 + 4)"}) == "84"


async def test_mcp_clock_returns_iso_local_time(mcp: InProcessMCPClient) -> None:
    stamp = await mcp.call_tool("clock", {})
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", stamp)


async def test_mcp_calculator_errors_are_not_exceptions_on_the_wire(
    mcp: InProcessMCPClient,
) -> None:
    with pytest.raises(ValueError, match="Division by zero"):
        await mcp.call_tool("calculator", {"expression": "1 / 0"})


async def test_allowlist_blocks_unknown_before_mcp(mcp: InProcessMCPClient) -> None:
    with pytest.raises(ValueError, match="allowlist"):
        await execute_tool("shell", {"cmd": "ls"}, client=mcp)


async def test_mcp_save_note_writes_file(mcp: InProcessMCPClient, tmp_path: Path) -> None:
    message = await mcp.call_tool("save_note", {"text": "Buy milk", "title": "todo"})
    assert message.startswith("Saved note ")
    raw = (tmp_path / "notes.jsonl").read_text(encoding="utf-8")
    assert "Buy milk" in raw


async def test_process_singleton_server_is_stable() -> None:
    assert get_mcp_server("data/a.jsonl") is get_mcp_server("data/a.jsonl")
    assert get_mcp_server("data/a.jsonl") is not get_mcp_server("data/b.jsonl")


def test_mcp_sdk_imports_after_windows_bootstrap() -> None:
    from app.mcp.windows import ensure_pywin32

    ensure_pywin32()
    from mcp import Client
    from mcp.server.mcpserver import MCPServer

    assert Client is not None
    assert MCPServer is not None
