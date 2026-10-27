"""Provider-agnostic embedding interface.

An embedding model maps text to a fixed-length vector such that semantically similar texts
land close together. Documents are embedded once at ingestion time; the user's question is
embedded at query time with the *same* model so the two live in the same vector space.

The interface deliberately separates ``embed_documents`` from ``embed_query`` because many
retrieval models (including nomic-embed-text) are trained with different prefixes for the
two sides, and asymmetric handling measurably improves recall.
"""

from typing import Protocol, runtime_checkable

Vector = list[float]


class EmbeddingUnavailableError(RuntimeError):
    """Raised when the embedding runtime cannot be reached or fails to respond."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    async def embed_documents(self, texts: list[str]) -> list[Vector]:
        """Embed passages for indexing. Returns one vector per input, in order."""
        ...

    async def embed_query(self, text: str) -> Vector:
        """Embed a search query so it can be compared against indexed passages."""
        ...

    async def health(self) -> bool:
        """True if the runtime is reachable and the embedding model is available."""
        ...
