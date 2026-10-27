"""Deterministic embedding provider for tests.

Produces a hashed bag-of-words vector: each lower-cased word is hashed to one of ``dim``
buckets and the vector is L2-normalised. Texts sharing words therefore have a higher cosine
similarity, which is enough to make retrieval tests meaningful without any model.
"""

import hashlib
import math
import re

from app.embeddings.base import Vector

_WORD = re.compile(r"[a-z0-9]+")


class FakeEmbeddingProvider:
    def __init__(self, *, dim: int = 64, model: str = "fake-embed", healthy: bool = True):
        self.dim = dim
        self._model = model
        self.healthy = healthy
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    @property
    def model_name(self) -> str:
        return self._model

    def _vector(self, text: str) -> Vector:
        vector = [0.0] * self.dim
        for word in _WORD.findall(text.lower()):
            digest = hashlib.sha1(word.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    async def embed_documents(self, texts: list[str]) -> list[Vector]:
        self.document_calls.append(list(texts))
        return [self._vector(t) for t in texts]

    async def embed_query(self, text: str) -> Vector:
        self.query_calls.append(text)
        return self._vector(text)

    async def health(self) -> bool:
        return self.healthy
