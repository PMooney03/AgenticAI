"""Allowlisted tools exposed as an MCP server.

Handlers stay small and side-effect free. Write/state-changing tools wait for Phase 6
(human approval). There is no shell tool.
"""

from datetime import datetime
from functools import lru_cache

from app.mcp.windows import ensure_pywin32

ensure_pywin32()

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from app.agent.tools.calculator import CalculatorError, calculate

SERVER_NAME = "agentic-second-brain"


def build_mcp_server() -> MCPServer:
    server = MCPServer(SERVER_NAME)

    @server.tool(
        name="calculator",
        description="Evaluate a basic arithmetic expression (+ - * / // % ** and parentheses).",
    )
    def calculator(expression: str) -> str:
        try:
            return calculate(expression)
        except CalculatorError as exc:
            raise ToolError(str(exc)) from exc

    @server.tool(
        name="clock",
        description="Return the current local date and time as an ISO-8601 string.",
    )
    def clock() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    return server


@lru_cache
def get_mcp_server() -> MCPServer:
    return build_mcp_server()
