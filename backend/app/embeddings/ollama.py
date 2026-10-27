"""Local embeddings served by Ollama (default model: ``nomic-embed-text``).

Uses Ollama's ``POST /api/embed`` endpoint directly through ``httpx``. Keeping this a plain
HTTP call (rather than a framework wrapper) makes the request/response shape visible and
trivial to mock in tests.

Model note: nomic-embed-text is trained with task prefixes. Passages are prefixed with
``search_document:`` and queries with ``search_query:``. Other models ignore unknown text
harmlessly, but the prefixes are only applied when the configured model is a nomic one.
"""

import logging
import time

import httpx

from app.embeddings.base import EmbeddingUnavailableError, Vector

logger = logging.getLogger(__name__)

_DOCUMENT_PREFIX = "search_document: "
_QUERY_PREFIX = "search_query: "


class LocalEmbeddingProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        batch_size: int = 32,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._batch_size = max(1, batch_size)
        self._timeout = timeout_seconds
        self._use_prefixes = "nomic" in model.lower()

    @property
    def model_name(self) -> str:
        return self._model

    async def embed_documents(self, texts: list[str]) -> list[Vector]:
        if not texts:
            return []
        prefixed = [self._prefix(t, _DOCUMENT_PREFIX) for t in texts]
        vectors: list[Vector] = []
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for start in range(0, len(prefixed), self._batch_size):
                batch = prefixed[start : start + self._batch_size]
                vectors.extend(await self._embed(client, batch))
        logger.info(
            "embeddings_computed",
            extra={
                "embedding_model": self._model,
                "count": len(texts),
                "embedding_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return vectors

    async def embed_query(self, text: str) -> Vector:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            vectors = await self._embed(client, [self._prefix(text, _QUERY_PREFIX)])
        return vectors[0]

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
                names = {m.get("name", "") for m in response.json().get("models", [])}
        except (httpx.HTTPError, ValueError):
            return False
        wanted = self._model if ":" in self._model else f"{self._model}:latest"
        return wanted in names

    # -- internals ---------------------------------------------------------------------

    def _prefix(self, text: str, prefix: str) -> str:
        return f"{prefix}{text}" if self._use_prefixes else text

    async def _embed(self, client: httpx.AsyncClient, inputs: list[str]) -> list[Vector]:
        try:
            response = await client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": inputs},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EmbeddingUnavailableError(
                f"Embedding request failed for model '{self._model}' at {self._base_url}: {exc}"
            ) from exc

        vectors = payload.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(inputs):
            raise EmbeddingUnavailableError(
                f"Embedding response malformed: expected {len(inputs)} vectors, "
                f"got {len(vectors) if isinstance(vectors, list) else 'none'}"
            )
        return [[float(x) for x in vector] for vector in vectors]
