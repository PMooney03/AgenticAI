"""Allowlisted tools exposed as an MCP server.

Read-only tools (calculator, clock) run immediately. ``save_note`` writes to the local
notebook and is marked ``requires_approval`` in the application allowlist; LangGraph
interrupts before this handler is called. There is no shell tool.
"""

from datetime import datetime
from functools import lru_cache
from pathlib import Path

from app.mcp.windows import ensure_pywin32

ensure_pywin32()

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from app.agent.tools.calculator import CalculatorError, calculate
from app.notes.store import NoteError, NoteStore

SERVER_NAME = "agentic-second-brain"


def build_mcp_server(*, notes_path: Path | None = None) -> MCPServer:
    server = MCPServer(SERVER_NAME)
    store = NoteStore(notes_path or Path("data/notes.jsonl"))

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

    @server.tool(
        name="save_note",
        description=(
            "Save a short note to the local notebook. This writes to disk and requires "
            "human approval before it runs."
        ),
    )
    def save_note(text: str, title: str = "") -> str:
        try:
            note = store.append(text=text, title=title)
        except NoteError as exc:
            raise ToolError(str(exc)) from exc
        return f"Saved note {note.id}."

    return server


@lru_cache
def get_mcp_server(notes_path: str = "data/notes.jsonl") -> MCPServer:
    return build_mcp_server(notes_path=Path(notes_path))
