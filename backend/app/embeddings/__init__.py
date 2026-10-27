"""Embedding provider abstraction.

Retrieval code depends only on :class:`EmbeddingProvider`; swapping the model or runtime
(Ollama today, sentence-transformers or a hosted API later) is a one-class change.
"""

from app.embeddings.base import EmbeddingProvider, EmbeddingUnavailableError
from app.embeddings.fake import FakeEmbeddingProvider
from app.embeddings.ollama import LocalEmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "EmbeddingUnavailableError",
    "FakeEmbeddingProvider",
    "LocalEmbeddingProvider",
]
