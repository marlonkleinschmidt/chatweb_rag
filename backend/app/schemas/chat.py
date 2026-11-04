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
    # Omitting the field keeps the current behaviour (PRD §12.6): sources
    # are shown, so existing clients do not change.
    show_sources: bool = Field(default=True)


class ChatStreamRequest(ChatRequest):
    """`ChatRequest` of the streaming endpoint, which never shows sources.

    Only the default changes (PRD §12.8, decision 1): omitting `show_sources`
    already answers without sources; an explicit `true` is rejected by the
    route with `stream_sources_unsupported`.
    """

    show_sources: bool = Field(default=False)


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
