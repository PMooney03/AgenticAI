import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import Response

from app.dependencies import DocumentRegistryDep, IngestionServiceDep
from app.embeddings import EmbeddingUnavailableError
from app.ingestion import DocumentRecord
from app.retrieval import VectorStoreUnavailableError
from app.schemas.chat import ErrorResponse
from app.schemas.documents import DocumentListResponse, DocumentResponse
from app.security import FileTooLargeError, FileValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

_UPLOAD_READ_CHUNK = 1024 * 1024


def _to_response(record: DocumentRecord) -> DocumentResponse:
    return DocumentResponse(
        id=record.id,
        name=record.name,
        content_type=record.content_type,
        size_bytes=record.size_bytes,
        status=record.status,
        chunk_count=record.chunk_count,
        page_count=record.page_count,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def _iter_upload(upload: UploadFile) -> AsyncIterator[bytes]:
    while block := await upload.read(_UPLOAD_READ_CHUNK):
        yield block


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index a PDF, TXT or Markdown document",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_413_CONTENT_TOO_LARGE: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def upload_document(file: UploadFile, service: IngestionServiceDep) -> DocumentResponse:
    try:
        record = await service.ingest(filename=file.filename, stream=_iter_upload(file))
    except FileTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
    except FileValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (EmbeddingUnavailableError, VectorStoreUnavailableError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Indexing is unavailable: check that Ollama (embedding model) and Qdrant "
            "are running.",
        ) from exc
    except ValueError as exc:
        # e.g. no extractable text; the registry already holds a 'failed' record.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    finally:
        await file.close()
    return _to_response(record)


@router.get("", response_model=DocumentListResponse, summary="List uploaded documents")
async def list_documents(registry: DocumentRegistryDep) -> DocumentListResponse:
    records = registry.list()
    return DocumentListResponse(documents=[_to_response(r) for r in records], total=len(records))


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get one document",
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def get_document(document_id: str, registry: DocumentRegistryDep) -> DocumentResponse:
    record = registry.get(document_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return _to_response(record)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and its indexed chunks",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def delete_document(document_id: str, service: IngestionServiceDep) -> Response:
    try:
        deleted = await service.delete(document_id)
    except VectorStoreUnavailableError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Vector store is unavailable."
        ) from exc
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
