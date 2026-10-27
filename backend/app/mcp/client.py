"""MCP client used by the agent.

``InProcessMCPClient`` talks to our ``MCPServer`` over the SDK's in-memory transport.
That is still MCP (initialize, tools/list, tools/call) without a second process.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.mcp.windows import ensure_pywin32

ensure_pywin32()

from mcp import Client
from mcp.server.mcpserver import MCPServer


class MCPClient(Protocol):
    async def list_remote_tools(self) -> list[str]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any] | None) -> str: ...


def text_from_call(result: Any) -> str:
    parts: list[str] = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


class InProcessMCPClient:
    def __init__(self, server: MCPServer) -> None:
        self._server = server

    async def list_remote_tools(self) -> list[str]:
        async with Client(self._server) as client:
            listed = await client.list_tools()
            return [tool.name for tool in listed.tools]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None) -> str:
        # Raise *after* leaving the session so MCP's task group is not still open.
        async with Client(self._server) as client:
            result = await client.call_tool(name, arguments or {})
            text = text_from_call(result)
            failed = bool(getattr(result, "is_error", False))
        if failed:
            raise ValueError(text or f"MCP tool '{name}' failed.")
        return text
