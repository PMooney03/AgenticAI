"""LangGraph state.

Plain dict keys so the graph is easy to print and explain. Values that travel between
nodes are JSON-serialisable (no RetrievedChunk objects in state).
"""

from typing import Any, Literal, TypedDict

Action = Literal["retrieve", "tool", "answer"]


class WorkflowStep(TypedDict):
    id: str
    node: str
    label: str
    done: bool


class AgentState(TypedDict, total=False):
    question: str
    history: list[dict[str, str]]
    use_documents: bool
    top_k: int | None
    max_steps: int
    step_count: int
    next_action: Action
    tool_name: str
    tool_args: dict[str, Any]
    attempted: list[str]
    chunks: list[dict[str, Any]]
    retrieval_ms: int
    tool_results: list[dict[str, str]]
    steps: list[WorkflowStep]
    nodes_visited: list[str]
    answer: str
    sources: list[dict[str, Any]]
    cited_labels: list[int]
    prompt_version: str
    model: str
    llm_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None


def initial_state(
    *,
    question: str,
    history: list[dict[str, str]],
    use_documents: bool,
    top_k: int | None,
    max_steps: int,
) -> AgentState:
    return AgentState(
        question=question,
        history=history,
        use_documents=use_documents,
        top_k=top_k,
        max_steps=max_steps,
        step_count=0,
        next_action="answer",
        tool_name="",
        tool_args={},
        attempted=[],
        chunks=[],
        retrieval_ms=0,
        tool_results=[],
        steps=[],
        nodes_visited=[],
        answer="",
        sources=[],
        cited_labels=[],
        prompt_version="",
        model="",
        llm_ms=0,
        prompt_tokens=None,
        completion_tokens=None,
    )


def append_step(
    state: AgentState, *, node: str, label: str, step_id: str, done: bool = True
) -> list[WorkflowStep]:
    steps = list(state.get("steps") or [])
    steps.append(WorkflowStep(id=step_id, node=node, label=label, done=done))
    return steps
