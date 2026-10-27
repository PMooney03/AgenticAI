from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: str
    name: str
    content_type: str
    size_bytes: int
    status: Literal["processing", "ready", "failed"]
    chunk_count: int
    page_count: int | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int = Field(ge=0)
