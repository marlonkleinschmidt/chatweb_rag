"""Document lifecycle: upload, background indexing, listing, removal, startup."""

import hashlib
import io
import logging
import threading
import time
import uuid
from pathlib import PureWindowsPath
from typing import Any, BinaryIO
from uuid import UUID

from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document as LCDocument
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app import db
from app.core.config import settings
from app.core.errors import AppError, ErrorCode, error_message
from app.schemas.document import Document, DocumentUploadResponse

logger = logging.getLogger(__name__)

PDF_EXTENSION = '.pdf'
PDF_MAGIC = b'%PDF-'
BYTES_PER_MB = 1024 * 1024
# RF-08: a PDF whose pages all extract fewer characters than this has no text.
MIN_PAGE_TEXT_CHARS = 20
CHROMA_COLLECTION_METADATA = {'hnsw:space': 'cosine'}
PROVIDER_TIMEOUT_ERROR = 'APITimeoutError'
PROVIDER_PACKAGE = 'openai'
DUPLICATE_WARNING = 'Este arquivo já foi enviado.'
# Documents still waiting for or running indexing cannot be removed (PRD §5.2).
UNFINISHED_STATUSES = ('received', 'processing')
# Chroma would otherwise send anonymous usage telemetry (privacy, PRD §7).
CHROMA_CLIENT_SETTINGS = ChromaSettings(anonymized_telemetry=False)

# Only one document is indexed at a time (PRD §7.4).
_index_lock = threading.Lock()


def _display_name(filename: str | None) -> str:
    # PureWindowsPath splits on both `/` and `\`, dropping any client path.
    return PureWindowsPath(filename or '').name.strip()


def _read_limited(stream: BinaryIO, max_bytes: int) -> bytes:
    """Read at most `max_bytes + 1` bytes, enough to detect an oversized file."""
    content = stream.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise AppError(ErrorCode.FILE_TOO_LARGE, n=settings.max_upload_mb)
    return content


def _count_pages(content: bytes) -> int:
    """Open the PDF with pypdf, rejecting unreadable, encrypted or long files."""
    try:
        reader = PdfReader(io.BytesIO(content))
        encrypted = reader.is_encrypted
        page_count = 0 if encrypted else len(reader.pages)
    except Exception as exc:  # any parse failure means the file is not a usable PDF
        raise AppError(ErrorCode.FILE_NOT_PDF) from exc
    if encrypted:
        raise AppError(ErrorCode.PDF_ENCRYPTED)
    if page_count > settings.max_pdf_pages:
        raise AppError(ErrorCode.PDF_TOO_MANY_PAGES, n=settings.max_pdf_pages)
    return page_count


def upload_document(filename: str | None, stream: BinaryIO) -> DocumentUploadResponse:
    """Validate an uploaded PDF (RF-02), store it and register it as `received`.

    Raises `AppError` with the PRD §5.3 code for each rejected case. Duplicates
    (same SHA-256) are accepted as new documents, with `warning` set.
    """
    content = _read_limited(stream, settings.max_upload_mb * BYTES_PER_MB)
    if not content:
        raise AppError(ErrorCode.FILE_EMPTY)

    display_name = _display_name(filename)
    if not display_name.lower().endswith(PDF_EXTENSION):
        raise AppError(ErrorCode.FILE_NOT_PDF)
    if not content.startswith(PDF_MAGIC):
        raise AppError(ErrorCode.FILE_NOT_PDF)
    page_count = _count_pages(content)

    sha256 = hashlib.sha256(content).hexdigest()
    duplicate = db.sha256_exists(sha256)
    document_id = str(uuid.uuid4())
    storage_path = f'{document_id}{PDF_EXTENSION}'
    file_path = settings.documents_dir / storage_path
    file_path.write_bytes(content)
    try:
        row = db.create(
            document_id=document_id,
            filename=display_name,
            storage_path=storage_path,
            sha256=sha256,
            size_bytes=len(content),
        )
    except Exception:
        file_path.unlink(missing_ok=True)
        raise

    logger.info(
        'document_received document_id=%s size_bytes=%d page_count=%d duplicate=%s',
        document_id,
        len(content),
        page_count,
        duplicate,
    )
    return DocumentUploadResponse.model_validate(
        {**row, 'warning': DUPLICATE_WARNING if duplicate else None}
    )


class IndexingError(Exception):
    """Indexing failure carrying the stable code stored on the document."""

    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def _embeddings() -> OpenAIEmbeddings:
    """OpenAI embeddings client; fails with `provider_error` when not configured."""
    if settings.openai_api_key is None or not settings.embedding_model:
        raise IndexingError(ErrorCode.PROVIDER_ERROR)
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        timeout=settings.provider_timeout_s,
        max_retries=1,
    )


def get_vector_store(*, with_embeddings: bool = True) -> Chroma:
    """Open the single persistent Chroma collection (PRD §8.2).

    Pass `with_embeddings=False` for operations that need no embedding calls
    (get/delete), so they also work without an OpenAI key.
    """
    return Chroma(
        collection_name=settings.chroma_collection,
        embedding_function=_embeddings() if with_embeddings else None,
        persist_directory=str(settings.chroma_dir),
        collection_metadata=CHROMA_COLLECTION_METADATA,
        client_settings=CHROMA_CLIENT_SETTINGS,
    )


def delete_vectors(document_id: str) -> None:
    """Delete every vector of `document_id`; idempotent (no-op when none exist)."""
    store = get_vector_store(with_embeddings=False)
    store.delete(where={'document_id': document_id})


def provider_error_code(exc: BaseException) -> ErrorCode | None:
    """Map an OpenAI SDK exception (raised through langchain-openai) to a code.

    Classes are matched by module/name so `openai` is not a direct dependency.
    """
    for cls in type(exc).__mro__:
        if cls.__name__ == PROVIDER_TIMEOUT_ERROR:
            return ErrorCode.PROVIDER_TIMEOUT
    for cls in type(exc).__mro__:
        if cls.__module__.split('.')[0] == PROVIDER_PACKAGE:
            return ErrorCode.PROVIDER_ERROR
    return None


def _load_pages(file_path: str) -> list[LCDocument]:
    """Extract one LangChain document per page, with 1-based `page` metadata."""
    try:
        pages = PyPDFLoader(file_path, mode='page').load()
    except Exception as exc:
        raise IndexingError(ErrorCode.INTERNAL_ERROR) from exc
    for page in pages:
        page.metadata['page'] = int(page.metadata.get('page', 0)) + 1
    if all(len(page.page_content.strip()) < MIN_PAGE_TEXT_CHARS for page in pages):
        raise IndexingError(ErrorCode.PDF_NO_TEXT)
    return pages


def _split(
    document_id: str, filename: str, pages: list[LCDocument]
) -> list[LCDocument]:
    """Split pages into chunks with exactly the PRD §8.2 metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
    )
    now = db.utc_now()
    chunks: list[LCDocument] = []
    for chunk_index, piece in enumerate(splitter.split_documents(pages)):
        chunks.append(
            LCDocument(
                page_content=piece.page_content,
                metadata={
                    'document_id': document_id,
                    'filename': filename,
                    'page': piece.metadata['page'],
                    'chunk_index': chunk_index,
                    'embedding_model': settings.embedding_model,
                    'created_at': now,
                    'updated_at': now,
                },
            )
        )
    return chunks


def _index(document_id: str, row: dict[str, object]) -> tuple[int, int]:
    """Run PRD §6.1 steps 2-5 and return `(page_count, chunk_count)`."""
    file_path = settings.documents_dir / str(row['storage_path'])
    pages = _load_pages(str(file_path))
    chunks = _split(document_id, str(row['filename']), pages)
    store = get_vector_store()
    ids = [f'{document_id}:{chunk.metadata["chunk_index"]}' for chunk in chunks]
    try:
        store.add_documents(chunks, ids=ids)
    except Exception as exc:
        code = provider_error_code(exc)
        if code is None:
            raise
        raise IndexingError(code) from exc
    return len(pages), len(chunks)


def _discard_vectors(document_id: str) -> None:
    """Best-effort removal of a document's vectors; logs instead of raising."""
    try:
        delete_vectors(document_id)
    except Exception as exc:
        logger.error(
            'vector_cleanup_failed document_id=%s exc_type=%s',
            document_id,
            type(exc).__name__,
        )


def _fail(document_id: str, code: ErrorCode) -> None:
    """Remove partial vectors and mark the document `failed` with a safe message."""
    _discard_vectors(document_id)
    db.update_status(
        document_id, 'failed', error_code=code.value, error_message=error_message(code)
    )


def index_document(document_id: str) -> None:
    """Background task: index a `received` document (PRD §6.1).

    Runs one document at a time. Every failure ends in `failed` with a stable
    `error_code`; nothing is raised to the caller.
    """
    with _index_lock:
        row = db.get(document_id)
        if row is None or not db.update_status(document_id, 'processing'):
            logger.info('index_skipped document_id=%s', document_id)
            return
        started = time.monotonic()
        try:
            page_count, chunk_count = _index(document_id, row)
        except Exception as exc:
            code = (
                exc.code if isinstance(exc, IndexingError) else ErrorCode.INTERNAL_ERROR
            )
            _fail(document_id, code)
            logger.warning(
                'index_failed document_id=%s error_code=%s exc_type=%s duration_ms=%d',
                document_id,
                code.value,
                type(exc.__cause__ or exc).__name__,
                (time.monotonic() - started) * 1000,
            )
            return
        if not db.update_status(
            document_id, 'ready', page_count=page_count, chunk_count=chunk_count
        ):
            # The row changed under us (e.g. marked failed); drop the new vectors.
            _discard_vectors(document_id)
            logger.warning('index_discarded document_id=%s', document_id)
            return
        logger.info(
            'index_ready document_id=%s page_count=%d chunk_count=%d duration_ms=%d',
            document_id,
            page_count,
            chunk_count,
            (time.monotonic() - started) * 1000,
        )


def _get_row(document_id: str) -> dict[str, Any]:
    """Return the row, or raise `404 document_not_found` (also for non-UUID IDs)."""
    try:
        canonical_id = str(UUID(document_id))
    except ValueError as exc:
        raise AppError(ErrorCode.DOCUMENT_NOT_FOUND) from exc
    row = db.get(canonical_id)
    if row is None:
        raise AppError(ErrorCode.DOCUMENT_NOT_FOUND)
    return row


def list_documents() -> list[Document]:
    """All documents, most recent first (PRD §5.1)."""
    return [Document.model_validate(row) for row in db.list()]


def get_document(document_id: str) -> Document:
    """One document; raises `404 document_not_found` when it does not exist."""
    return Document.model_validate(_get_row(document_id))


def delete_document(document_id: str) -> None:
    """Remove vectors, file and row, in this order (PRD §8.3).

    Each step is idempotent, so a repeated call after `delete_partial` re-runs
    all of them. Raises `409 document_processing` for unfinished documents.
    """
    row = _get_row(document_id)
    document_id = row['id']
    if row['status'] in UNFINISHED_STATUSES:
        raise AppError(ErrorCode.DOCUMENT_PROCESSING)
    step = 'vectors'
    try:
        delete_vectors(document_id)
        step = 'file'
        (settings.documents_dir / row['storage_path']).unlink(missing_ok=True)
        step = 'record'
        db.delete(document_id)
    except Exception as exc:
        logger.error(
            'delete_failed document_id=%s step=%s error_code=%s exc_type=%s',
            document_id,
            step,
            ErrorCode.DELETE_PARTIAL.value,
            type(exc).__name__,
        )
        raise AppError(ErrorCode.DELETE_PARTIAL) from exc
    logger.info('document_deleted document_id=%s', document_id)


def fail_interrupted_documents() -> None:
    """Startup: documents left in `received`/`processing` become `failed`."""
    code = ErrorCode.PROCESSING_INTERRUPTED
    for document_id in db.fail_unfinished(code.value, error_message(code)):
        _discard_vectors(document_id)
        logger.warning(
            'document_interrupted document_id=%s error_code=%s',
            document_id,
            code.value,
        )


def embedding_model_changed() -> bool:
    """PRD §8.3: True if any vector used another `EMBEDDING_MODEL`.

    Reads only the metadata of at most one vector; never raises (False on error).
    """
    if not settings.embedding_model:
        return False
    try:
        result = get_vector_store(with_embeddings=False).get(
            where={'embedding_model': {'$ne': settings.embedding_model}},
            limit=1,
            include=['metadatas'],
        )
    except Exception as exc:
        logger.error('embedding_model_check_failed exc_type=%s', type(exc).__name__)
        return False
    return bool(result['ids'])


def check_embedding_model() -> None:
    """Startup (PRD §8.3): log a warning when the embedding model changed."""
    if embedding_model_changed():
        logger.warning('embedding_model_mismatch vectors_found=true')
