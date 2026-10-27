"""Vector store interface.

The store knows nothing about embedding models; it receives vectors and payloads and
returns payloads with similarity scores. That keeps Qdrant (or any replacement) behind one
small contract that the RAG pipeline and, later, the LangGraph agent depend on.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.embeddings.base import Vector
from app.ingestion.chunking import Chunk


class VectorStoreUnavailableError(RuntimeError):
    """Raised when the vector database cannot be reached or rejects the operation."""


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_name: str
    chunk_index: int
    text: str
    score: float
    page: int | None = None


@runtime_checkable
class VectorStore(Protocol):
    async def upsert(self, chunks: list[Chunk], vectors: list[Vector]) -> None:
        """Insert or replace chunks (matched by ``chunk_id``) with their vectors."""
        ...

    async def search(
        self, vector: Vector, *, top_k: int, score_threshold: float | None = None
    ) -> list[RetrievedChunk]:
        """Return the ``top_k`` most similar chunks, best first."""
        ...

    async def delete_document(self, document_id: str) -> None:
        """Remove every chunk belonging to a document."""
        ...

    async def count(self) -> int:
        """Total number of stored chunks."""
        ...

    async def health(self) -> bool: ...
