"""Document ingestion: load -> chunk -> embed -> store, with a registry of documents."""

from app.ingestion.chunking import Chunk, chunk_pages
from app.ingestion.loaders import LoadedPage, UnsupportedFileError, load_pages
from app.ingestion.registry import DocumentRecord, DocumentRegistry, DocumentStatus
from app.ingestion.service import IngestionService

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
