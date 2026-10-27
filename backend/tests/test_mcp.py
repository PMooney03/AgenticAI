import re

import pytest

from app.agent.tools.policy import execute_tool
from app.mcp.client import InProcessMCPClient
from app.mcp.server import build_mcp_server, get_mcp_server


@pytest.fixture
def mcp() -> InProcessMCPClient:
    return InProcessMCPClient(build_mcp_server())


async def test_mcp_lists_allowlisted_tools(mcp: InProcessMCPClient) -> None:
    names = await mcp.list_remote_tools()
    assert names == ["calculator", "clock"]


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


async def test_process_singleton_server_is_stable() -> None:
    assert get_mcp_server() is get_mcp_server()


def test_mcp_sdk_imports_after_windows_bootstrap() -> None:
    from app.mcp.windows import ensure_pywin32

    ensure_pywin32()
    from mcp import Client
    from mcp.server.mcpserver import MCPServer

    assert Client is not None
    assert MCPServer is not None
