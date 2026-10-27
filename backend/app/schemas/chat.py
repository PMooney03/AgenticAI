from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_MESSAGE_CHARS = 8_000
MAX_HISTORY_TURNS = 20

ChatMode = Literal["rag", "chat"]


class WorkflowEvent(BaseModel):
    id: str
    node: str
    label: str
    done: bool = True


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
        examples=["What does the report say about Q3 revenue?"],
    )
    history: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=MAX_HISTORY_TURNS,
        description="Prior turns, oldest first. The server is stateless.",
    )
    use_documents: bool = Field(
        default=True,
        description="Retrieve from uploaded documents and ground the answer (RAG). "
        "Set false for a plain conversation with the model.",
    )
    top_k: int | None = Field(
        default=None, ge=1, le=20, description="Override the number of chunks to retrieve."
    )


class SourceResponse(BaseModel):
    label: int = Field(description="Matches [Source N] citations in the answer.")
    document_id: str
    document_name: str
    page: int | None
    score: float = Field(description="Cosine similarity between question and chunk.")
    snippet: str
    cited: bool = Field(description="Whether the answer actually referenced this source.")


class RetrievalStats(BaseModel):
    retrieved_chunks: int
    retrieval_ms: int
    cited_sources: int


class QualityStats(BaseModel):
    citation_rate: float | None = None
    groundedness: float | None = None
    refused: bool = False


class PendingApproval(BaseModel):
    tool: str
    description: str
    preview: str = Field(
        default="",
        description="Human-visible proposal (e.g. note text). Not stored in traces.",
    )


class ChatResponse(BaseModel):
    answer: str
    mode: ChatMode
    model: str
    prompt_version: str
    request_id: str
    latency_ms: int = Field(ge=0, description="LLM call time in milliseconds.")
    sources: list[SourceResponse] = Field(default_factory=list)
    retrieval: RetrievalStats | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    quality: QualityStats | None = None
    workflow: list[WorkflowEvent] = Field(
        default_factory=list,
        description="High-level LangGraph steps. Never includes chain-of-thought.",
    )
    pending_approval: PendingApproval | None = None


class ErrorResponse(BaseModel):
    detail: str
    request_id: str | None = None
