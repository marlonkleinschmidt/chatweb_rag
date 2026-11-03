from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

DocumentStatus = Literal['received', 'processing', 'ready', 'failed']


class Document(BaseModel):
    """Public view of a catalog row. `storage_path` and `sha256` stay internal."""

    id: UUID
    filename: str
    status: DocumentStatus
    error_code: str | None = None
    error_message: str | None = None
    page_count: int | None = Field(default=None, ge=0)
    chunk_count: int | None = Field(default=None, ge=0)
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(Document):
    """`POST /documents` response: a `Document` plus the RF-01 duplicate warning."""

    warning: str | None = None


class DocumentListResponse(BaseModel):
    items: list[Document]
    # PRD §8.3: some vectors were made with another `EMBEDDING_MODEL`.
    embedding_model_changed: bool = False
