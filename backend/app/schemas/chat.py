from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.core.config import MIN_DOCUMENTS_PER_QUERY, MIN_QUESTION_CHARS, settings

Question = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=MIN_QUESTION_CHARS,
        max_length=settings.max_question_chars,
    ),
]


class ChatRequest(BaseModel):
    """A single, independent question; no previous messages are sent."""

    question: Question
    document_ids: list[UUID] = Field(
        min_length=MIN_DOCUMENTS_PER_QUERY,
        max_length=settings.max_documents_per_query,
    )


class Source(BaseModel):
    index: int = Field(ge=1)
    document_id: UUID
    filename: str
    page: int | None = Field(default=None, ge=1)
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    has_evidence: bool
    sources: list[Source]
