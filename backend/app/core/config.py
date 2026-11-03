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
    retrieval_k: int = Field(default=8, gt=0)
    relevance_threshold: float = Field(default=0.35, ge=0.0, le=1.0)

    # Chat limits
    max_question_chars: int = Field(default=2000, ge=MIN_QUESTION_CHARS)
    max_documents_per_query: int = Field(default=10, ge=MIN_DOCUMENTS_PER_QUERY)
    excerpt_max_chars: int = Field(default=500, gt=0)

    # Storage
    chroma_collection: str = 'documents'
    documents_dir: Path = Path('data/documents')
    chroma_dir: Path = Path('data/chroma')
    sqlite_path: Path = Path('data/app.db')

    # Network
    cors_origins: list[str] = ['http://localhost:5173']
    api_host: str = '127.0.0.1'


settings = Settings()
