"""Retriever: the one object the rest of the app uses to find relevant chunks.

It pairs an :class:`EmbeddingProvider` with a :class:`VectorStore` and records timings so
the observability layer can report retrieval latency separately from LLM latency.
"""

import logging
import time
from dataclasses import dataclass, field

from app.embeddings.base import EmbeddingProvider
from app.retrieval.base import RetrievedChunk, VectorStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    embedding_ms: int = 0
    search_ms: int = 0

    @property
    def total_ms(self) -> int:
        return self.embedding_ms + self.search_ms


class Retriever:
    def __init__(
        self,
        *,
        embeddings: EmbeddingProvider,
        store: VectorStore,
        default_top_k: int = 4,
        score_threshold: float | None = None,
    ) -> None:
        self._embeddings = embeddings
        self._store = store
        self._default_top_k = default_top_k
        self._score_threshold = score_threshold

    async def retrieve(self, query: str, *, top_k: int | None = None) -> RetrievalResult:
        k = top_k or self._default_top_k

        started = time.perf_counter()
        vector = await self._embeddings.embed_query(query)
        embedding_ms = int((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        chunks = await self._store.search(vector, top_k=k, score_threshold=self._score_threshold)
        search_ms = int((time.perf_counter() - started) * 1000)

        logger.info(
            "retrieval_completed",
            extra={
                "embedding_model": self._embeddings.model_name,
                "top_k": k,
                "retrieved_chunks": len(chunks),
                "embedding_ms": embedding_ms,
                "search_ms": search_ms,
            },
        )
        return RetrievalResult(chunks=chunks, embedding_ms=embedding_ms, search_ms=search_ms)
