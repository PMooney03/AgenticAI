import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.dependencies import LLMProviderDep, RAGPipelineDep
from app.embeddings import EmbeddingUnavailableError
from app.llm import ChatMessage, LLMUnavailableError
from app.prompts import get_prompt
from app.retrieval import VectorStoreUnavailableError
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    RetrievalStats,
    SourceResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def history_to_messages(request: ChatRequest) -> list[ChatMessage]:
    return [ChatMessage(role=m.role, content=m.content) for m in request.history]


def build_chat_messages(request: ChatRequest) -> tuple[list[ChatMessage], str]:
    """Plain-chat conversation: system prompt, history, user message. Pure function."""
    prompt = get_prompt("chat-system")
    messages: list[ChatMessage] = [ChatMessage(role="system", content=prompt.render())]
    messages.extend(history_to_messages(request))
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
    summary="Ask a question (grounded in your documents by default)",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
)
async def chat(
    payload: ChatRequest, request: Request, llm: LLMProviderDep, rag: RAGPipelineDep
) -> ChatResponse:
    request_id: str = request.state.request_id
    mode = "rag" if payload.use_documents else "chat"

    logger.info(
        "chat_started",
        extra={
            "mode": mode,
            "model": llm.model_name,
            "history_turns": len(payload.history),
            "message_chars": len(payload.message),
        },
    )

    try:
        if payload.use_documents:
            return await _answer_with_documents(payload, request_id, rag)
        return await _answer_plain(payload, request_id, llm)
    except LLMUnavailableError as exc:
        logger.error("chat_llm_unavailable", extra={"mode": mode, "error": str(exc)})
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=_LLM_DOWN) from exc
    except (EmbeddingUnavailableError, VectorStoreUnavailableError) as exc:
        logger.error("chat_retrieval_unavailable", extra={"mode": mode, "error": str(exc)})
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=_RETRIEVAL_DOWN) from exc


async def _answer_plain(payload: ChatRequest, request_id: str, llm: LLMProviderDep) -> ChatResponse:
    messages, prompt_version = build_chat_messages(payload)
    result = await llm.chat(messages)
    logger.info(
        "chat_completed",
        extra={
            "mode": "chat",
            "model": result.model,
            "prompt_version": prompt_version,
            "llm_latency_ms": result.latency_ms,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "answer_chars": len(result.content),
        },
    )
    return ChatResponse(
        answer=result.content,
        mode="chat",
        model=result.model,
        prompt_version=prompt_version,
        request_id=request_id,
        latency_ms=result.latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


async def _answer_with_documents(
    payload: ChatRequest, request_id: str, rag: RAGPipelineDep
) -> ChatResponse:
    result = await rag.answer(
        payload.message, history=history_to_messages(payload), top_k=payload.top_k
    )
    cited = set(result.cited_labels)
    return ChatResponse(
        answer=result.answer,
        mode="rag",
        model=result.model,
        prompt_version=result.prompt_version,
        request_id=request_id,
        latency_ms=result.llm_ms,
        sources=[
            SourceResponse(
                label=s.label,
                document_id=s.document_id,
                document_name=s.document_name,
                page=s.page,
                score=s.score,
                snippet=s.snippet,
                cited=s.label in cited,
            )
            for s in result.sources
        ],
        retrieval=RetrievalStats(
            retrieved_chunks=result.retrieved_chunks,
            retrieval_ms=result.retrieval_ms,
            cited_sources=len(cited),
        ),
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
