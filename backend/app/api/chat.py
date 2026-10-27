import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.dependencies import LLMProviderDep
from app.llm import ChatMessage, LLMUnavailableError
from app.prompts import get_prompt
from app.schemas.chat import ChatRequest, ChatResponse, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def build_chat_messages(request: ChatRequest) -> tuple[list[ChatMessage], str]:
    """Assemble the conversation sent to the model.

    Returns the messages and the prompt version used, so callers can report/log it.
    Kept as a pure function so it is trivially unit-testable.
    """
    prompt = get_prompt("chat-system")
    messages: list[ChatMessage] = [ChatMessage(role="system", content=prompt.render())]
    messages.extend(ChatMessage(role=m.role, content=m.content) for m in request.history)
    messages.append(ChatMessage(role="user", content=request.message))
    return messages, prompt.version


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with the local model",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
)
async def chat(payload: ChatRequest, request: Request, llm: LLMProviderDep) -> ChatResponse:
    request_id: str = request.state.request_id
    messages, prompt_version = build_chat_messages(payload)

    logger.info(
        "chat_started",
        extra={
            "model": llm.model_name,
            "prompt_version": prompt_version,
            "history_turns": len(payload.history),
            "message_chars": len(payload.message),
        },
    )

    try:
        result = await llm.chat(messages)
    except LLMUnavailableError as exc:
        logger.error(
            "chat_llm_unavailable",
            extra={"model": llm.model_name, "prompt_version": prompt_version, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The language model is currently unavailable. Check that Ollama is running "
            "and the configured model is pulled.",
        ) from exc

    logger.info(
        "chat_completed",
        extra={
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
        model=result.model,
        prompt_version=prompt_version,
        request_id=request_id,
        latency_ms=result.latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
