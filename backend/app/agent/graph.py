"""Compile and run the LangGraph.

Whiteboard version::

    START -> plan
               |-- retrieve --> evaluate --\\
               |-- call_tool --> evaluate --+--> plan (if more needed and budget left)
               |-- generate_answer <-------/
                             |
                            END
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import NodeFns
from app.agent.routing import route_after_evaluate, route_after_plan
from app.agent.state import AgentState, WorkflowStep, initial_state
from app.agent.tools.policy import ToolRunner
from app.llm.base import LLMProvider
from app.retrieval.retriever import Retriever


def build_graph(nodes: NodeFns):
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
    return graph.compile()


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
        max_steps: int = 3,
    ) -> None:
        self._llm = llm
        self._retriever = retriever
        self._max_steps = max_steps
        if tools is None:
            from app.mcp.client import InProcessMCPClient
            from app.mcp.server import get_mcp_server

            tools = InProcessMCPClient(get_mcp_server())
        self._app = build_graph(NodeFns(llm=llm, retriever=retriever, mcp=tools))

    async def run(
        self,
        *,
        question: str,
        history: list[dict[str, str]],
        use_documents: bool = True,
        top_k: int | None = None,
    ) -> AgentResult:
        start = initial_state(
            question=question,
            history=history,
            use_documents=use_documents,
            top_k=top_k,
            max_steps=self._max_steps,
        )
        final: AgentState = await self._app.ainvoke(start)
        return AgentResult(
            answer=str(final.get("answer") or ""),
            model=str(final.get("model") or self._llm.model_name),
            prompt_version=str(final.get("prompt_version") or ""),
            steps=list(final.get("steps") or []),
            nodes_visited=list(final.get("nodes_visited") or []),
            sources=list(final.get("sources") or []),
            cited_labels=list(final.get("cited_labels") or []),
            retrieved_chunks=len(final.get("chunks") or []),
            retrieval_ms=int(final.get("retrieval_ms") or 0),
            llm_ms=int(final.get("llm_ms") or 0),
            prompt_tokens=final.get("prompt_tokens"),
            completion_tokens=final.get("completion_tokens"),
            tool_calls=list(final.get("tool_results") or []),
        )
