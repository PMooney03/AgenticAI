from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_MESSAGE_CHARS = 8_000
MAX_HISTORY_TURNS = 20


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        min_length=1,
        max_length=MAX_MESSAGE_CHARS,
        description="The user's new message.",
        examples=["Explain what a vector database is in two sentences."],
    )
    history: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=MAX_HISTORY_TURNS,
        description="Prior turns, oldest first. The server is stateless in Phase 1.",
    )


class ChatResponse(BaseModel):
    answer: str
    model: str
    prompt_version: str
    request_id: str
    latency_ms: int = Field(ge=0, description="End-to-end LLM call time in milliseconds.")
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ErrorResponse(BaseModel):
    detail: str
    request_id: str | None = None
