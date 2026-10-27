from typing import Literal

from pydantic import BaseModel


class OllamaStatus(BaseModel):
    reachable: bool
    model: str
    base_url: str


class EmbeddingStatus(BaseModel):
    reachable: bool
    model: str


class QdrantStatus(BaseModel):
    reachable: bool
    url: str
    collection: str
    chunks: int | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    ollama: OllamaStatus
    embeddings: EmbeddingStatus
    qdrant: QdrantStatus
    documents_ready: int
