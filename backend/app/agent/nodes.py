"""LangGraph node implementations.

Each node returns a partial state update. High-level ``steps`` are the only thing the UI
sees; planner rationale never leaves this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.agent.routing import decide_plan
from app.agent.state import AgentState, WorkflowStep, append_step
from app.agent.tools.policy import TOOLS, ToolRunner, execute_tool, list_tools
from app.llm.base import ChatMessage, LLMProvider, LLMResult
from app.prompts import get_prompt
from app.rag.context import build_context
from app.rag.pipeline import build_rag_messages, extract_citations
from app.retrieval.base import RetrievedChunk
from app.retrieval.retriever import Retriever


def _history(state: AgentState) -> list[ChatMessage]:
    return [
        ChatMessage(role=turn["role"], content=turn["content"])  # type: ignore[arg-type]
        for turn in state.get("history") or []
        if turn.get("role") in {"user", "assistant"} and turn.get("content")
    ]


def _evidence_blob(state: AgentState) -> str:
    parts: list[str] = []
    chunks = state.get("chunks") or []
    if chunks:
        parts.append(f"{len(chunks)} document chunks already retrieved.")
    for result in state.get("tool_results") or []:
        parts.append(f"tool {result.get('name')}: {result.get('output', '')[:400]}")
    return "\n".join(parts) if parts else "(none yet)"


def _chunk_from_dict(payload: dict[str, Any]) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=str(payload.get("chunk_id", "")),
        document_id=str(payload.get("document_id", "")),
        document_name=str(payload.get("document_name", "")),
        chunk_index=int(payload.get("chunk_index", 0)),
        text=str(payload.get("text", "")),
        score=float(payload.get("score", 0.0)),
        page=payload.get("page"),
    )


def _step(state: AgentState, *, node: str, label: str) -> list[WorkflowStep]:
    n = len(state.get("steps") or [])
    return append_step(state, node=node, label=label, step_id=f"{node}-{n}")


def _accumulate_usage(state: AgentState, result: LLMResult) -> dict[str, Any]:
    prompt = (state.get("prompt_tokens") or 0) + (result.prompt_tokens or 0)
    completion = (state.get("completion_tokens") or 0) + (result.completion_tokens or 0)
    return {
        "model": result.model,
        "llm_ms": int(state.get("llm_ms") or 0) + result.latency_ms,
        "prompt_tokens": prompt or None,
        "completion_tokens": completion or None,
    }


@dataclass
class NodeFns:
    llm: LLMProvider
    retriever: Retriever
    mcp: ToolRunner

    async def plan(self, state: AgentState) -> dict[str, Any]:
        prompt = get_prompt("agent-planner")
        tool_names = ", ".join(spec.name for spec in list_tools()) or "(none)"
        documents_allowed = "true" if state.get("use_documents") else "false"
        system = prompt.render(
            tool_names=tool_names,
            documents_allowed=documents_allowed,
            evidence=_evidence_blob(state),
        )
        messages = [ChatMessage(role="system", content=system), *_history(state)]
        messages.append(ChatMessage(role="user", content=state["question"]))
        result = await self.llm.chat(messages)
        decision = decide_plan(result.content, use_documents=bool(state.get("use_documents")))
        return {
            "next_action": decision.action,
            "tool_name": decision.tool_name or "",
            "tool_args": decision.tool_args,
            "step_count": int(state.get("step_count") or 0) + 1,
            "prompt_version": prompt.version,
            "nodes_visited": [*(state.get("nodes_visited") or []), "plan"],
            "steps": _step(state, node="plan", label="Analysed request"),
            **_accumulate_usage(state, result),
        }

    async def retrieve(self, state: AgentState) -> dict[str, Any]:
        retrieval = await self.retriever.retrieve(state["question"], top_k=state.get("top_k"))
        chunks = [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "document_name": chunk.document_name,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "score": chunk.score,
                "page": chunk.page,
            }
            for chunk in retrieval.chunks
        ]
        n = len(chunks)
        steps = _step(state, node="retrieve", label="Searched documents")
        steps = _step(
            {**state, "steps": steps},
            node="retrieve",
            label="Retrieved 1 chunk" if n == 1 else f"Retrieved {n} chunks",
        )
        attempted = list(dict.fromkeys([*(state.get("attempted") or []), "retrieve"]))
        return {
            "chunks": chunks,
            "retrieval_ms": int(state.get("retrieval_ms") or 0) + retrieval.total_ms,
            "attempted": attempted,
            "nodes_visited": [*(state.get("nodes_visited") or []), "retrieve"],
            "steps": steps,
        }

    async def call_tool(self, state: AgentState) -> dict[str, Any]:
        name = state.get("tool_name") or ""
        args = state.get("tool_args") or {}
        spec = TOOLS.get(name)
        try:
            output = await execute_tool(name, args, client=self.mcp)
            ok = True
        except ValueError as exc:
            output = str(exc)
            ok = False
        label = f"Used {name} tool" if spec else "Rejected unknown tool"
        results = list(state.get("tool_results") or [])
        results.append(
            {
                "name": name,
                "output": output,
                "ok": "true" if ok else "false",
            }
        )
        attempted = list(dict.fromkeys([*(state.get("attempted") or []), "tool"]))
        return {
            "tool_results": results,
            "attempted": attempted,
            "nodes_visited": [*(state.get("nodes_visited") or []), "call_tool"],
            "steps": _step(state, node="call_tool", label=label),
        }

    async def evaluate(self, state: AgentState) -> dict[str, Any]:
        return {
            "nodes_visited": [*(state.get("nodes_visited") or []), "evaluate"],
            "steps": _step(state, node="evaluate", label="Evaluated results"),
        }

    async def generate_answer(self, state: AgentState) -> dict[str, Any]:
        chunks = [_chunk_from_dict(item) for item in state.get("chunks") or []]
        context, sources = build_context(chunks)
        tool_results = state.get("tool_results") or []
        history = _history(state)

        attempted = set(state.get("attempted") or [])
        if tool_results:
            prompt = get_prompt("agent-answer")
            blob = "\n".join(f"- {item.get('name')}: {item.get('output')}" for item in tool_results)
            system = prompt.render(tool_results=blob, context=context)
            messages = [ChatMessage(role="system", content=system), *history]
            messages.append(ChatMessage(role="user", content=state["question"]))
            version = prompt.version
        elif chunks or "retrieve" in attempted:
            messages, version = build_rag_messages(
                question=state["question"], context=context, history=history
            )
        else:
            prompt = get_prompt("chat-system")
            messages = [ChatMessage(role="system", content=prompt.render()), *history]
            messages.append(ChatMessage(role="user", content=state["question"]))
            version = prompt.version

        result = await self.llm.chat(messages)
        source_dicts = [
            {
                "label": source.label,
                "chunk_id": source.chunk_id,
                "document_id": source.document_id,
                "document_name": source.document_name,
                "page": source.page,
                "score": source.score,
                "snippet": source.snippet,
            }
            for source in sources
        ]
        cited = extract_citations(result.content, available=len(sources))
        usage = _accumulate_usage(state, result)
        return {
            "answer": result.content,
            "sources": source_dicts,
            "cited_labels": cited,
            "prompt_version": version,
            "nodes_visited": [*(state.get("nodes_visited") or []), "generate_answer"],
            "steps": _step(state, node="generate_answer", label="Generated response"),
            **usage,
        }


def evidence_json(state: AgentState) -> str:
    """Debug helper for tests; not shown in the UI."""
    return json.dumps(
        {
            "chunks": len(state.get("chunks") or []),
            "tools": [item.get("name") for item in state.get("tool_results") or []],
        }
    )
