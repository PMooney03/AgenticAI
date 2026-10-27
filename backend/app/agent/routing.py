"""Pure routing helpers — the part you draw on a whiteboard.

No I/O. Tests cover these without LangGraph or an LLM.
"""

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.tools.policy import TOOLS

Action = Literal["retrieve", "tool", "answer"]

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class PlanDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Action
    tool_name: str | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_plan(raw: str) -> PlanDecision:
    """Best-effort parse of the planner's JSON. Invalid output becomes ``answer``."""
    match = _JSON_OBJECT.search(_strip_fences(raw))
    if not match:
        return PlanDecision(action="answer")
    try:
        payload = json.loads(match.group(0))
        if not isinstance(payload, dict):
            return PlanDecision(action="answer")
        return PlanDecision.model_validate(payload)
    except (json.JSONDecodeError, ValidationError):
        return PlanDecision(action="answer")


def decide_plan(raw: str, *, use_documents: bool) -> PlanDecision:
    """Parse, clamp, and fall back when the model did not emit JSON.

    A missing plan is treated as ``retrieve`` when documents are allowed so a
    garbled planner does not skip the user's library. Explicit JSON still wins.
    """
    if not _JSON_OBJECT.search(_strip_fences(raw)):
        return PlanDecision(action="retrieve" if use_documents else "answer")
    return clamp_decision(parse_plan(raw), use_documents=use_documents)


def clamp_decision(decision: PlanDecision, *, use_documents: bool) -> PlanDecision:
    """Enforce tool allowlist and the documents gate after the model has chosen."""
    action = decision.action
    tool_name = (decision.tool_name or "").strip()
    if action == "retrieve" and not use_documents:
        action = "answer"
    if action == "tool" and tool_name not in TOOLS:
        action = "answer"
        tool_name = ""
    return PlanDecision(action=action, tool_name=tool_name or None, tool_args=decision.tool_args)


def route_after_plan(state: dict[str, Any]) -> Action:
    action = state.get("next_action") or "answer"
    if action not in {"retrieve", "tool", "answer"}:
        return "answer"
    if state.get("step_count", 0) >= state.get("max_steps", 3) and action != "answer":
        return "answer"
    return action  # type: ignore[return-value]


def route_after_evaluate(state: dict[str, Any]) -> Literal["plan", "answer"]:
    """Loop only when we still have budget and no usable evidence."""
    if state.get("step_count", 0) >= state.get("max_steps", 3):
        return "answer"
    if state.get("chunks") or state.get("tool_results"):
        return "answer"
    attempted = set(state.get("attempted") or [])
    if "retrieve" in attempted and "tool" in attempted:
        return "answer"
    if attempted == {"retrieve"} or attempted == {"tool"}:
        return "plan"
    return "answer"
