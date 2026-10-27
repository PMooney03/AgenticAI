"""LangGraph agent: plan, optionally retrieve or call a tool, evaluate, answer.

``Agent`` / ``AgentResult`` are imported lazily so ``TraceStore`` and routing helpers
can load without pulling retrieval/RAG (avoids an import cycle).
"""

from typing import Any

from app.agent.routing import (
    PlanDecision,
    decide_plan,
    parse_plan,
    route_after_evaluate,
    route_after_plan,
)
from app.agent.tools.policy import list_tools
from app.agent.trace import TraceStore

__all__ = [
    "Agent",
    "AgentResult",
    "PlanDecision",
    "TraceStore",
    "decide_plan",
    "list_tools",
    "parse_plan",
    "route_after_evaluate",
    "route_after_plan",
]


def __getattr__(name: str) -> Any:
    if name in {"Agent", "AgentResult"}:
        from app.agent.graph import Agent, AgentResult

        return Agent if name == "Agent" else AgentResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
