from pydantic import BaseModel, Field


class LatencyStats(BaseModel):
    count: int
    avg_ms: float | None = None
    p50_ms: float | None = None
    p95_ms: float | None = None
    max_ms: float | None = None


class MetricsSnapshot(BaseModel):
    chats: int
    chats_completed: int
    chats_paused: int
    chats_rag: int
    chats_refused: int
    http_requests: int
    http_errors: int
    tool_calls: int
    approvals_approved: int
    approvals_rejected: int
    prompt_tokens: int
    completion_tokens: int
    llm: LatencyStats
    retrieval: LatencyStats
    citation_rate_avg: float | None = None
    groundedness_avg: float | None = None
    tools: dict[str, int] = Field(default_factory=dict)
    routes: dict[str, int] = Field(default_factory=dict)
