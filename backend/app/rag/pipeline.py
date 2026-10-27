"""The standard RAG pipeline.

    question -> embed -> vector search -> build grounded context -> LLM -> answer + sources

Phase 4 wraps this same retriever and prompt inside a LangGraph agent that *decides* whether
retrieval is needed; this class remains the straightforward "always retrieve" path.
"""

import logging
import re
from dataclasses import dataclass, field

from app.llm.base import ChatMessage, LLMProvider
from app.prompts import get_prompt
from app.rag.context import Source, build_context
from app.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)

_CITATION = re.compile(r"\[Source\s+(\d+)\]", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class RAGResult:
    answer: str
    model: str
    prompt_version: str
    sources: list[Source] = field(default_factory=list)
    cited_labels: list[int] = field(default_factory=list)
    retrieved_chunks: int = 0
    retrieval_ms: int = 0
    llm_ms: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def build_rag_messages(
    *, question: str, context: str, history: list[ChatMessage] | None = None
) -> tuple[list[ChatMessage], str]:
    """System prompt with context, then prior turns, then the question. Pure function."""
    prompt = get_prompt("rag-system")
    messages = [ChatMessage(role="system", content=prompt.render(context=context))]
    messages.extend(history or [])
    messages.append(ChatMessage(role="user", content=question))
    return messages, prompt.version


def extract_citations(answer: str, available: int) -> list[int]:
    """Distinct ``[Source N]`` labels the answer actually cites, in order of appearance."""
    seen: list[int] = []
    for match in _CITATION.finditer(answer):
        label = int(match.group(1))
        if 1 <= label <= available and label not in seen:
            seen.append(label)
    return seen


class RAGPipeline:
    def __init__(self, *, retriever: Retriever, llm: LLMProvider) -> None:
        self._retriever = retriever
        self._llm = llm

    async def answer(
        self, question: str, *, history: list[ChatMessage] | None = None, top_k: int | None = None
    ) -> RAGResult:
        retrieval = await self._retriever.retrieve(question, top_k=top_k)
        context, sources = build_context(retrieval.chunks)
        messages, prompt_version = build_rag_messages(
            question=question, context=context, history=history
        )

        result = await self._llm.chat(messages)
        cited = extract_citations(result.content, available=len(sources))

        logger.info(
            "rag_completed",
            extra={
                "model": result.model,
                "prompt_version": prompt_version,
                "retrieved_chunks": len(retrieval.chunks),
                "cited_sources": len(cited),
                "retrieval_ms": retrieval.total_ms,
                "llm_latency_ms": result.latency_ms,
            },
        )
        return RAGResult(
            answer=result.content,
            model=result.model,
            prompt_version=prompt_version,
            sources=sources,
            cited_labels=cited,
            retrieved_chunks=len(retrieval.chunks),
            retrieval_ms=retrieval.total_ms,
            llm_ms=result.latency_ms,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
        )
