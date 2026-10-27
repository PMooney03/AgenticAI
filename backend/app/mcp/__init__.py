"""Local MCP server and in-process client.

The LangGraph agent never imports tool implementations. It names an allowlisted tool;
the MCP client calls the server. Tests and the FastAPI process use an in-memory
``Client(server)`` session (real MCP, no subprocess). ``python -m app.mcp`` serves
the same tools over stdio.
"""

from app.mcp.windows import ensure_pywin32

ensure_pywin32()

from app.mcp.client import InProcessMCPClient, MCPClient, text_from_call
from app.mcp.server import get_mcp_server

__all__ = [
    "InProcessMCPClient",
    "MCPClient",
    "get_mcp_server",
    "text_from_call",
]
