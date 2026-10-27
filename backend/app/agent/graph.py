"""Compile and run the LangGraph.

Whiteboard version::

    START -> plan
               |-- retrieve --> evaluate --\\
               |-- call_tool --> evaluate --+--> plan (if more needed and budget left)
               |-- generate_answer <-------/
                             |
                            END

``call_tool`` may ``interrupt()`` when the allowlist marks a tool ``requires_approval``.
Resume with ``Command(resume="approve"|"reject")`` on the same thread id.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agent.nodes import NodeFns
from app.agent.routing import route_after_evaluate, route_after_plan
from app.agent.state import AgentState, WorkflowStep, append_step, initial_state
from app.agent.tools.policy import ToolRunner
from app.llm.base import LLMProvider
from app.retrieval.retriever import Retriever


def build_graph(nodes: NodeFns, checkpointer: InMemorySaver):
    graph = StateGraph(AgentState)
    graph.add_node("plan", nodes.plan)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("call_tool", nodes.call_tool)
    graph.add_node("evaluate", nodes.evaluate)
    graph.add_node("generate_answer", nodes.generate_answer)

    graph.add_edge(START, "plan")
    graph.add_conditional_edges(
        "plan",
        route_after_plan,
        {"retrieve": "retrieve", "tool": "call_tool", "answer": "generate_answer"},
    )
    graph.add_edge("retrieve", "evaluate")
    graph.add_edge("call_tool", "evaluate")
    graph.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {"plan": "plan", "answer": "generate_answer"},
    )
    graph.add_edge("generate_answer", END)
    return graph.compile(checkpointer=checkpointer)


@dataclass(frozen=True, slots=True)
class AgentResult:
    answer: str
    model: str
    prompt_version: str
    steps: list[WorkflowStep]
    nodes_visited: list[str]
    sources: list[dict]
    cited_labels: list[int]
    retrieved_chunks: int
    retrieval_ms: int
    llm_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None
    tool_calls: list[dict] = field(default_factory=list)
    pending_approval: dict[str, str] | None = None
    thread_id: str = ""

    @property
    def mode(self) -> Literal["rag", "chat"]:
        return "rag" if "retrieve" in self.nodes_visited else "chat"

    @property
    def tool_names(self) -> list[str]:
        return [str(item.get("name")) for item in self.tool_calls if item.get("name")]


class Agent:
    def __init__(
        self,
        *,
        llm: LLMProvider,
        retriever: Retriever,
        tools: ToolRunner | None = None,
        checkpointer: InMemorySaver | None = None,
        max_steps: int = 3,
    ) -> None:
        self._llm = llm
        self._retriever = retriever
        self._max_steps = max_steps
        self._checkpointer = checkpointer or InMemorySaver()
        if tools is None:
            from app.mcp.client import InProcessMCPClient
            from app.mcp.server import get_mcp_server

            tools = InProcessMCPClient(get_mcp_server())
        self._app = build_graph(
            NodeFns(llm=llm, retriever=retriever, mcp=tools),
            self._checkpointer,
        )

    def _config(self, thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    async def run(
        self,
        *,
        question: str,
        history: list[dict[str, str]],
        use_documents: bool = True,
        top_k: int | None = None,
        thread_id: str | None = None,
    ) -> AgentResult:
        thread_id = thread_id or uuid.uuid4().hex
        start = initial_state(
            question=question,
            history=history,
            use_documents=use_documents,
            top_k=top_k,
            max_steps=self._max_steps,
        )
        config = self._config(thread_id)
        await self._app.ainvoke(start, config)
        return await self._collect(config)

    async def resume(self, thread_id: str, *, approved: bool) -> AgentResult:
        config = self._config(thread_id)
        snapshot = await self._app.aget_state(config)
        if not snapshot.interrupts:
            raise LookupError("No pending approval for that request.")
        await self._app.ainvoke(
            Command(resume="approve" if approved else "reject"),
            config,
        )
        return await self._collect(config)

    async def _collect(self, config: dict[str, Any]) -> AgentResult:
        snapshot = await self._app.aget_state(config)
        values: AgentState = snapshot.values or {}
        steps = list(values.get("steps") or [])
        pending: dict[str, str] | None = None
        if snapshot.interrupts:
            raw = snapshot.interrupts[0].value
            if isinstance(raw, dict):
                pending = {str(key): str(value) for key, value in raw.items()}
            else:
                pending = {"tool": "unknown", "description": str(raw), "preview": ""}
            steps = append_step(
                {**values, "steps": steps},
                node="call_tool",
                label="Waiting for approval",
                step_id="call_tool-pending",
                done=False,
            )
        thread_id = str(config["configurable"]["thread_id"])
        return AgentResult(
            answer=str(values.get("answer") or ""),
            model=str(values.get("model") or self._llm.model_name),
            prompt_version=str(values.get("prompt_version") or ""),
            steps=steps,
            nodes_visited=list(values.get("nodes_visited") or []),
            sources=list(values.get("sources") or []),
            cited_labels=list(values.get("cited_labels") or []),
            retrieved_chunks=len(values.get("chunks") or []),
            retrieval_ms=int(values.get("retrieval_ms") or 0),
            llm_ms=int(values.get("llm_ms") or 0),
            prompt_tokens=values.get("prompt_tokens"),
            completion_tokens=values.get("completion_tokens"),
            tool_calls=list(values.get("tool_results") or []),
            pending_approval=pending,
            thread_id=thread_id,
        )
