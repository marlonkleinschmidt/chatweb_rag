from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.core.config import MIN_DOCUMENTS_PER_QUERY, MIN_QUESTION_CHARS, settings

Question = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=MIN_QUESTION_CHARS,
        max_length=settings.max_question_chars,
    ),
]


MAX_HISTORY_MESSAGES = 2 * settings.max_history_turns


class ChatHistoryMessage(BaseModel):
    """One previous message of the conversation, sent by the client (RF-25)."""

    role: Literal['user', 'assistant']
    # Kept as sent: the character limit counts the raw content (PRD §13.6).
    content: str

    @field_validator('content')
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('content must not be blank')
        return value


class ChatRequest(BaseModel):
    """A question plus the optional recent conversation history (PRD §13).

    An empty or omitted `history` keeps the v2.2 behaviour: an independent
    question with no previous messages.
    """

    question: Question
    document_ids: list[UUID] = Field(
        min_length=MIN_DOCUMENTS_PER_QUERY,
        max_length=settings.max_documents_per_query,
    )
    # Omitting the field keeps the current behaviour (PRD §12.6): sources
    # are shown, so existing clients do not change.
    show_sources: bool = Field(default=True)
    history: list[ChatHistoryMessage] = Field(
        default_factory=list,
        max_length=MAX_HISTORY_MESSAGES,
        description=(
            'Previous messages of the conversation, in chronological order. '
            f'At most {MAX_HISTORY_MESSAGES} messages '
            f'(2 x MAX_HISTORY_TURNS) and {settings.max_history_chars} '
            'characters summed over all `content` values (MAX_HISTORY_CHARS); '
            '`content` must not be blank. Any violation returns '
            '422 history_invalid. Omitted or [] keeps the behaviour without '
            'history.'
        ),
    )

    @field_validator('history')
    @classmethod
    def history_within_char_limit(
        cls, value: list[ChatHistoryMessage]
    ) -> list[ChatHistoryMessage]:
        if sum(len(message.content) for message in value) > settings.max_history_chars:
            raise ValueError('history exceeds MAX_HISTORY_CHARS')
        return value


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
