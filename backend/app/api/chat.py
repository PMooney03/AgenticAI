import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.agent.graph import AgentResult
from app.agent.trace import TraceRecord
from app.dependencies import AgentDep
from app.embeddings import EmbeddingUnavailableError
from app.llm import ChatMessage, LLMUnavailableError
from app.observability.metrics import ChatObservation, MetricsStore
from app.prompts import get_prompt
from app.retrieval import VectorStoreUnavailableError
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    PendingApproval,
    QualityStats,
    RetrievalStats,
    SourceResponse,
    WorkflowEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def build_chat_messages(request: ChatRequest) -> tuple[list[ChatMessage], str]:
    """Plain-chat prompt construction. The live route always goes through the graph."""
    prompt = get_prompt("chat-system")
    messages: list[ChatMessage] = [ChatMessage(role="system", content=prompt.render())]
    messages.extend(ChatMessage(role=m.role, content=m.content) for m in request.history)
    messages.append(ChatMessage(role="user", content=request.message))
    return messages, prompt.version


_LLM_DOWN = (
    "The language model is currently unavailable. Check that Ollama is running and the "
    "configured model is pulled."
)
_RETRIEVAL_DOWN = (
    "Document retrieval is currently unavailable. Check that Qdrant and the Ollama embedding "
    "model are running, or set use_documents=false."
)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask a question (LangGraph decides retrieve vs tool vs answer)",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
)
async def chat(payload: ChatRequest, request: Request, agent: AgentDep) -> ChatResponse:
    request_id: str = request.state.request_id

    logger.info(
        "chat_started",
        extra={
            "use_documents": payload.use_documents,
            "history_turns": len(payload.history),
            "message_chars": len(payload.message),
        },
    )

    try:
        result = await agent.run(
            question=payload.message,
            history=[{"role": m.role, "content": m.content} for m in payload.history],
            use_documents=payload.use_documents,
            top_k=payload.top_k,
            thread_id=request_id,
        )
    except LLMUnavailableError as exc:
        logger.error("chat_llm_unavailable", extra={"error": str(exc)})
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=_LLM_DOWN) from exc
    except (EmbeddingUnavailableError, VectorStoreUnavailableError) as exc:
        logger.error("chat_retrieval_unavailable", extra={"error": str(exc)})
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=_RETRIEVAL_DOWN) from exc

    response = chat_response_from_result(result, request_id)
    _store_trace(request, result, request_id)
    record_agent_result(request, result, new=True)
    if result.pending_approval:
        logger.info(
            "chat_paused_for_approval",
            extra={
                "tool": result.pending_approval.get("tool"),
                "preview_chars": len(result.pending_approval.get("preview") or ""),
                "nodes": result.nodes_visited,
            },
        )
    else:
        logger.info(
            "chat_completed",
            extra={
                "mode": response.mode,
                "model": result.model,
                "prompt_version": result.prompt_version,
                "nodes": result.nodes_visited,
                "retrieved_chunks": result.retrieved_chunks,
                "tools": result.tool_names,
                "llm_latency_ms": result.llm_ms,
                "retrieval_ms": result.retrieval_ms,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "answer_chars": len(result.answer),
                "citation_rate": result.citation_rate,
                "groundedness": result.groundedness,
                "refused": result.refused,
            },
        )
    return response


def _metrics(request: Request) -> MetricsStore:
    return request.app.state.metrics


def record_agent_result(request: Request, result: AgentResult, *, new: bool) -> None:
    _metrics(request).observe_chat(
        ChatObservation(
            mode=result.mode,
            llm_ms=result.llm_ms,
            retrieval_ms=result.retrieval_ms,
            retrieved_chunks=result.retrieved_chunks,
            cited_sources=len(result.cited_labels),
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            tools=result.tool_names,
            paused=result.pending_approval is not None,
            refused=result.refused,
            citation_rate=result.citation_rate,
            groundedness=result.groundedness,
        ),
        new=new,
    )


def _store_trace(request: Request, result: AgentResult, request_id: str) -> None:
    request.app.state.traces.put(
        TraceRecord(
            request_id=request_id,
            nodes_visited=result.nodes_visited,
            workflow=[step for step in result.steps],
            retrieved_chunks=result.retrieved_chunks,
            tools=result.tool_names,
            prompt_version=result.prompt_version,
            model=result.model,
        )
    )


def chat_response_from_result(result: AgentResult, request_id: str) -> ChatResponse:
    cited = set(result.cited_labels)
    return ChatResponse(
        answer=result.answer,
        mode=result.mode,
        model=result.model,
        prompt_version=result.prompt_version,
        request_id=request_id,
        latency_ms=result.llm_ms,
        sources=[
            SourceResponse(
                label=int(source["label"]),
                document_id=str(source["document_id"]),
                document_name=str(source["document_name"]),
                page=source.get("page"),
                score=float(source["score"]),
                snippet=str(source["snippet"]),
                cited=int(source["label"]) in cited,
            )
            for source in result.sources
        ],
        retrieval=(
            RetrievalStats(
                retrieved_chunks=result.retrieved_chunks,
                retrieval_ms=result.retrieval_ms,
                cited_sources=len(cited),
            )
            if result.mode == "rag"
            else None
        ),
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        workflow=[
            WorkflowEvent(
                id=step["id"],
                node=step["node"],
                label=step["label"],
                done=bool(step.get("done", True)),
            )
            for step in result.steps
        ],
        pending_approval=(
            PendingApproval(
                tool=result.pending_approval["tool"],
                description=result.pending_approval.get("description") or "",
                preview=result.pending_approval.get("preview") or "",
            )
            if result.pending_approval
            else None
        ),
        quality=QualityStats(
            citation_rate=result.citation_rate,
            groundedness=result.groundedness,
            refused=result.refused,
        ),
    )
