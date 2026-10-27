"""Allowlisted tools.

The planner can only name tools that appear here. Execution is delegated to the MCP
client; unknown names never reach the server. Phase 6 will set ``requires_approval``
on anything that changes state.
"""

from dataclasses import dataclass
from typing import Any, Literal, Protocol


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
}


def list_tools() -> list[ToolSpec]:
    return sorted(TOOLS.values(), key=lambda spec: spec.name)


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
