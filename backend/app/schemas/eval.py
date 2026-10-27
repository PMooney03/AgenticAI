from datetime import UTC, datetime

from pydantic import BaseModel, Field


class EvalCaseResult(BaseModel):
    id: str
    passed: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    failures: list[str] = Field(default_factory=list)
    nodes_visited: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    retrieved_chunks: int = 0
    cited_sources: int = 0
    citation_rate: float | None = None
    groundedness: float | None = None
    refused: bool = False
    pending: bool = False
    llm_ms: int = 0


class EvalReport(BaseModel):
    ran_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    total: int
    passed: int
    failed: int
    duration_ms: int
    cases: list[EvalCaseResult] = Field(default_factory=list)
