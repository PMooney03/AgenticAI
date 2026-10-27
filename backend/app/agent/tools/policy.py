"""Allowlisted local tools.

Phase 5 will add MCP tools to this same registry. The planner can only name tools that
appear here; unknown names are rejected before anything runs.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agent.tools.calculator import CalculatorError, calculate


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    read_only: bool
    requires_approval: bool
    handler: Callable[..., str]


def _calculator(expression: str = "", **_ignored: Any) -> str:
    return calculate(str(expression))


TOOLS: dict[str, ToolSpec] = {
    "calculator": ToolSpec(
        name="calculator",
        description="Evaluate a basic arithmetic expression (+ - * / // % ** and parentheses).",
        read_only=True,
        requires_approval=False,
        handler=_calculator,
    )
}


def list_tools() -> list[ToolSpec]:
    return sorted(TOOLS.values(), key=lambda spec: spec.name)


def execute_tool(name: str, arguments: dict[str, Any] | None) -> str:
    spec = TOOLS.get(name)
    if spec is None:
        allowed = ", ".join(TOOLS)
        raise ValueError(f"Tool '{name}' is not on the allowlist. Allowed: {allowed}.")
    args = arguments or {}
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be an object.")
    try:
        return spec.handler(**args)
    except TypeError as exc:
        raise ValueError(f"Invalid arguments for '{name}': {exc}") from exc
    except CalculatorError as exc:
        raise ValueError(str(exc)) from exc
