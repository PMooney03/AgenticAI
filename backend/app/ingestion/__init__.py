"""Document ingestion: load -> chunk -> embed -> store, with a registry of documents.

``IngestionService`` is imported lazily so ``retrieval.base`` can load ``Chunk`` without
entering a cycle through this package.
"""

from typing import Any

from app.ingestion.chunking import Chunk, chunk_pages
from app.ingestion.loaders import LoadedPage, UnsupportedFileError, load_pages
from app.ingestion.registry import DocumentRecord, DocumentRegistry, DocumentStatus

__all__ = [
    "Chunk",
    "DocumentRecord",
    "DocumentRegistry",
    "DocumentStatus",
    "IngestionService",
    "LoadedPage",
    "UnsupportedFileError",
    "chunk_pages",
    "load_pages",
]


def __getattr__(name: str) -> Any:
    if name == "IngestionService":
        from app.ingestion.service import IngestionService

        return IngestionService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
