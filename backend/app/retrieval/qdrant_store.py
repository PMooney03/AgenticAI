"""Qdrant implementation of :class:`VectorStore`.

Collection layout
-----------------
- Point ID: the chunk's UUID (Qdrant requires UUIDs or integers).
- Vector: the chunk embedding, cosine distance.
- Payload: ``document_id``, ``document_name``, ``page``, ``chunk_index``, ``text`` plus any
  extra metadata. ``document_id`` has a keyword index so per-document deletes and filters
  are cheap.

The collection is created lazily on the first upsert, sized from the vector we receive, so
the store never needs to know the embedding dimension up front. ``location=":memory:"``
runs an in-process Qdrant for tests.
"""

import logging
import time

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.embeddings.base import Vector
from app.ingestion.chunking import Chunk
from app.retrieval.base import RetrievedChunk, VectorStoreUnavailableError

logger = logging.getLogger(__name__)

_CLIENT_ERRORS = (ResponseHandlingException, UnexpectedResponse, ConnectionError, OSError)


class QdrantVectorStore:
    def __init__(
        self,
        *,
        location: str,
        collection: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._collection = collection
        self._local_mode = location == ":memory:"
        if self._local_mode:
            self._client = AsyncQdrantClient(location=":memory:")
        else:
            self._client = AsyncQdrantClient(
                url=location, api_key=api_key, timeout=int(timeout_seconds)
            )
        self._ready = False

    @property
    def collection(self) -> str:
        return self._collection

    # -- VectorStore ---------------------------------------------------------------------

    async def upsert(self, chunks: list[Chunk], vectors: list[Vector]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if not chunks:
            return
        await self._ensure_collection(len(vectors[0]))

        points = [
            models.PointStruct(
                id=chunk.chunk_id,
                vector=vector,
                payload={
                    "document_id": chunk.document_id,
                    "document_name": chunk.document_name,
                    "page": chunk.page,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    **chunk.metadata,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        started = time.perf_counter()
        try:
            await self._client.upsert(self._collection, points=points, wait=True)
        except _CLIENT_ERRORS as exc:
            raise VectorStoreUnavailableError(f"Qdrant upsert failed: {exc}") from exc
        logger.info(
            "qdrant_upsert",
            extra={
                "collection": self._collection,
                "points": len(points),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

    async def search(
        self, vector: Vector, *, top_k: int, score_threshold: float | None = None
    ) -> list[RetrievedChunk]:
        if not await self._collection_exists():
            return []
        try:
            response = await self._client.query_points(
                self._collection,
                query=vector,
                limit=top_k,
                score_threshold=score_threshold if score_threshold else None,
                with_payload=True,
            )
        except _CLIENT_ERRORS as exc:
            raise VectorStoreUnavailableError(f"Qdrant search failed: {exc}") from exc

        results: list[RetrievedChunk] = []
        for point in response.points:
            payload = point.payload or {}
            results.append(
                RetrievedChunk(
                    chunk_id=str(point.id),
                    document_id=str(payload.get("document_id", "")),
                    document_name=str(payload.get("document_name", "")),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    text=str(payload.get("text", "")),
                    score=float(point.score),
                    page=payload.get("page"),
                )
            )
        return results

    async def delete_document(self, document_id: str) -> None:
        if not await self._collection_exists():
            return
        try:
            await self._client.delete(
                self._collection,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id", match=models.MatchValue(value=document_id)
                            )
                        ]
                    )
                ),
                wait=True,
            )
        except _CLIENT_ERRORS as exc:
            raise VectorStoreUnavailableError(f"Qdrant delete failed: {exc}") from exc

    async def count(self) -> int:
        if not await self._collection_exists():
            return 0
        try:
            result = await self._client.count(self._collection, exact=True)
        except _CLIENT_ERRORS as exc:
            raise VectorStoreUnavailableError(f"Qdrant count failed: {exc}") from exc
        return int(result.count)

    async def health(self) -> bool:
        try:
            await self._client.get_collections()
        except Exception:  # noqa: BLE001 - any failure means "not healthy"
            return False
        return True

    async def close(self) -> None:
        await self._client.close()

    # -- internals -----------------------------------------------------------------------

    async def _collection_exists(self) -> bool:
        if self._ready:
            return True
        try:
            exists = await self._client.collection_exists(self._collection)
        except _CLIENT_ERRORS as exc:
            raise VectorStoreUnavailableError(f"Qdrant unreachable: {exc}") from exc
        self._ready = bool(exists)
        return self._ready

    async def _ensure_collection(self, dimension: int) -> None:
        if await self._collection_exists():
            info = await self._client.get_collection(self._collection)
            params = info.config.params.vectors
            existing = params.size if isinstance(params, models.VectorParams) else None
            if existing is not None and existing != dimension:
                raise VectorStoreUnavailableError(
                    f"Collection '{self._collection}' stores {existing}-d vectors but the "
                    f"embedding model produced {dimension}-d vectors. Delete the collection "
                    "or change EMBEDDING_MODEL."
                )
            return
        try:
            await self._client.create_collection(
                self._collection,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
            )
            if not self._local_mode:  # payload indexes are a no-op in the in-process store
                await self._client.create_payload_index(
                    self._collection,
                    field_name="document_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
        except _CLIENT_ERRORS as exc:
            raise VectorStoreUnavailableError(f"Qdrant collection setup failed: {exc}") from exc
        self._ready = True
        logger.info(
            "qdrant_collection_created",
            extra={"collection": self._collection, "dimension": dimension},
        )
