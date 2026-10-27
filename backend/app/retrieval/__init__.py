"""Retrieval: vector store abstraction, Qdrant implementation, and the Retriever facade."""

from app.retrieval.base import RetrievedChunk, VectorStore, VectorStoreUnavailableError
from app.retrieval.qdrant_store import QdrantVectorStore
from app.retrieval.retriever import RetrievalResult, Retriever

__all__ = [
    "QdrantVectorStore",
    "RetrievalResult",
    "RetrievedChunk",
    "Retriever",
    "VectorStore",
    "VectorStoreUnavailableError",
]
