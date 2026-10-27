"""Allowlisted tools.

The planner can only name tools that appear here. Execution is delegated to the MCP
client; unknown names never reach the server. Anything with ``requires_approval`` is
interrupted by LangGraph before ``tools/call``.
"""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

MAX_PREVIEW_CHARS = 400


class ToolRunner(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any] | None) -> str: ...


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    read_only: bool
    requires_approval: bool
    source: Literal["mcp"] = "mcp"


TOOLS: dict[str, ToolSpec] = {
    "calculator": ToolSpec(
        name="calculator",
        description="Evaluate a basic arithmetic expression (+ - * / // % ** and parentheses).",
        read_only=True,
        requires_approval=False,
    ),
    "clock": ToolSpec(
        name="clock",
        description="Return the current local date and time as an ISO-8601 string.",
        read_only=True,
        requires_approval=False,
    ),
    "save_note": ToolSpec(
        name="save_note",
        description="Save a short note to the local notebook. Requires human approval.",
        read_only=False,
        requires_approval=True,
    ),
}


def list_tools() -> list[ToolSpec]:
    return sorted(TOOLS.values(), key=lambda spec: spec.name)


def describe_approval(name: str, arguments: dict[str, Any] | None) -> dict[str, str]:
    """Human-facing payload for a LangGraph interrupt. Not stored in traces."""
    args = arguments or {}
    if name == "save_note":
        text = str(args.get("text") or "")
        title = str(args.get("title") or "").strip()
        description = "Save a note to the local notebook."
        if title:
            description = f'Save a note titled "{title[:80]}" to the local notebook.'
        return {
            "tool": name,
            "description": description,
            "preview": text[:MAX_PREVIEW_CHARS],
        }
    return {"tool": name, "description": f"Run the {name} tool.", "preview": ""}


async def execute_tool(
    name: str,
    arguments: dict[str, Any] | None,
    *,
    client: ToolRunner,
) -> str:
    spec = TOOLS.get(name)
    if spec is None:
        allowed = ", ".join(TOOLS)
        raise ValueError(f"Tool '{name}' is not on the allowlist. Allowed: {allowed}.")
    args = arguments or {}
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be an object.")
    return await client.call_tool(name, args)
