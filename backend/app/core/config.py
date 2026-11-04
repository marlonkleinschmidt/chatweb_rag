from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Fixed lower bounds from PRD §3 (only the upper bounds are configurable).
MIN_QUESTION_CHARS = 3
MIN_DOCUMENTS_PER_QUERY = 1


class Settings(BaseSettings):
    """Application settings read from the environment and `.env` (PRD §3)."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    # OpenAI. Optional at startup so `/health` works without a key;
    # the RAG service must fail with a safe error when they are missing.
    openai_api_key: SecretStr | None = None
    chat_model: str | None = None
    embedding_model: str | None = None
    chat_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    provider_timeout_s: float = Field(default=60.0, gt=0)

    # Upload limits
    max_upload_mb: int = Field(default=20, gt=0)
    max_pdf_pages: int = Field(default=500, gt=0)

    # RAG (validated in Sprint 3, see docs/eval.md)
    chunk_size: int = Field(default=500, gt=0)
    chunk_overlap: int = Field(default=200, ge=0)
    # Task 7.33: a 1-page document whose extracted text has at most this many
    # characters is indexed as a single chunk (0 disables it).
    small_document_max_chars: int = Field(default=4000, ge=0)
    retrieval_k: int = Field(default=8, gt=0)
    relevance_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    # Task 7.29: with 2+ selected documents, each one keeps up to this many of
    # its own chunks above the threshold inside `retrieval_k` (0 disables it).
    min_chunks_per_document: int = Field(default=1, ge=0)

    # Chat limits
    max_question_chars: int = Field(default=2000, ge=MIN_QUESTION_CHARS)
    max_documents_per_query: int = Field(default=10, ge=MIN_DOCUMENTS_PER_QUERY)
    excerpt_max_chars: int = Field(default=500, gt=0)

    # Conversation history (PRD §13): at most `2 * max_history_turns`
    # messages and `max_history_chars` characters summed over their content.
    max_history_turns: int = Field(default=4, ge=0)
    max_history_chars: int = Field(default=4000, ge=0)
    # Task 8.3: rewrite follow-up questions before retrieval (needs history).
    query_rewrite_enabled: bool = True

    # Storage
    chroma_collection: str = 'documents'
    documents_dir: Path = Path('data/documents')
    chroma_dir: Path = Path('data/chroma')
    sqlite_path: Path = Path('data/app.db')

    # Network
    cors_origins: list[str] = ['http://localhost:5173']
    api_host: str = '127.0.0.1'


settings = Settings()
