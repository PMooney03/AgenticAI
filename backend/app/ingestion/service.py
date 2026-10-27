"""Ingestion orchestration: validate -> persist -> load -> chunk -> embed -> upsert.

Runs synchronously within the upload request (documents are small and local). The registry
records ``processing`` first so a crash mid-way leaves a visible ``failed`` entry rather than
a silent gap.
"""

import asyncio
import logging
import shutil
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from app.embeddings.base import EmbeddingProvider
from app.ingestion.chunking import chunk_pages
from app.ingestion.loaders import load_pages
from app.ingestion.registry import DocumentRecord, DocumentRegistry
from app.retrieval.base import VectorStore
from app.security.files import FileTooLargeError, validate_upload

logger = logging.getLogger(__name__)

_SNIFF_BYTES = 4096
_COPY_CHUNK = 1024 * 1024


class IngestionService:
    def __init__(
        self,
        *,
        registry: DocumentRegistry,
        store: VectorStore,
        embeddings: EmbeddingProvider,
        upload_dir: Path,
        max_upload_bytes: int,
        chunk_size: int,
        chunk_overlap: int,
    ) -> None:
        self._registry = registry
        self._store = store
        self._embeddings = embeddings
        self._upload_dir = upload_dir
        self._max_bytes = max_upload_bytes
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    async def ingest(self, *, filename: str | None, stream: AsyncIterator[bytes]) -> DocumentRecord:
        """Ingest an upload. Raises ``FileValidationError`` for rejected files."""
        document_id = uuid.uuid4().hex
        target_dir = self._upload_dir / document_id
        target_dir.mkdir(parents=True, exist_ok=True)
        temp_path = target_dir / "upload.part"

        try:
            size, head = await self._spool(stream, temp_path)
            validated = validate_upload(
                filename=filename, size_bytes=size, head=head, max_bytes=self._max_bytes
            )
            final_path = target_dir / validated.safe_name
            temp_path.rename(final_path)
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

        record = self._registry.create(
            document_id=document_id,
            name=validated.safe_name,
            content_type=validated.content_type,
            size_bytes=validated.size_bytes,
        )
        logger.info(
            "ingestion_started",
            extra={
                "document_id": document_id,
                "content_type": validated.content_type,
                "size_bytes": validated.size_bytes,
            },
        )

        started = time.perf_counter()
        try:
            pages = await asyncio.to_thread(load_pages, final_path)
            chunks = await asyncio.to_thread(
                chunk_pages,
                pages,
                document_id=document_id,
                document_name=validated.safe_name,
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
                extra_metadata={"content_type": validated.content_type},
            )
            if not chunks:
                raise ValueError("No extractable text found (scanned PDF without OCR?).")

            vectors = await self._embeddings.embed_documents([c.text for c in chunks])
            await self._store.upsert(chunks, vectors)
        except Exception as exc:
            self._registry.mark_failed(document_id, error=_public_error(exc))
            logger.error(
                "ingestion_failed",
                extra={"document_id": document_id, "error": str(exc)},
            )
            raise

        page_count = len({p.page for p in pages if p.page is not None}) or None
        self._registry.mark_ready(document_id, chunk_count=len(chunks), page_count=page_count)
        logger.info(
            "ingestion_completed",
            extra={
                "document_id": document_id,
                "pages": page_count,
                "chunks": len(chunks),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        updated = self._registry.get(document_id)
        return updated or record

    async def delete(self, document_id: str) -> bool:
        record = self._registry.get(document_id)
        if record is None:
            return False
        await self._store.delete_document(document_id)
        shutil.rmtree(self._upload_dir / document_id, ignore_errors=True)
        self._registry.delete(document_id)
        logger.info("document_deleted", extra={"document_id": document_id})
        return True

    # -- internals -----------------------------------------------------------------------

    async def _spool(self, stream: AsyncIterator[bytes], path: Path) -> tuple[int, bytes]:
        """Write the stream to disk, enforcing the size cap as bytes arrive."""
        size = 0
        head = b""
        with path.open("wb") as handle:
            async for block in stream:
                size += len(block)
                if size > self._max_bytes:
                    raise FileTooLargeError(
                        f"File exceeds the {self._max_bytes // (1024 * 1024)} MB limit."
                    )
                if len(head) < _SNIFF_BYTES:
                    head += block[: _SNIFF_BYTES - len(head)]
                handle.write(block)
        return size, head


def _public_error(exc: Exception) -> str:
    """A short, non-sensitive description safe to store and show to the user."""
    name = type(exc).__name__
    message = str(exc)
    if len(message) > 200:
        message = message[:200] + "..."
    return f"{name}: {message}" if message else name
