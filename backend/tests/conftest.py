"""Shared fixtures: isolation from `backend/data` and the real OpenAI key.

The environment variables below are set at import time, BEFORE any `app`
module is imported (pytest imports this file first, and pydantic-settings
gives environment variables priority over the `.env` in the CWD). This
guarantees that, even when pytest runs from `backend/` with a real `.env`:

- the settings singleton never points its data paths at `backend/data`;
- no test can use the real OpenAI key or model names (retrieval and the LLM
  are faked in the tests, and background indexing never runs).

Per-test isolation is done by repointing the `settings` attributes at
`tmp_path` (every consumer reads them at call time, so no module reload is
needed), which keeps each test's catalog, PDFs and Chroma vectors separate.
"""

import atexit
import io
import logging
import os
import shutil
import tempfile
import uuid

_SESSION_DIR = tempfile.mkdtemp(prefix='rag-pytest-')

# Safety net for the import-time singleton: env vars override `.env`, so the
# data paths never resolve to `backend/data` even before the first fixture.
os.environ['OPENAI_API_KEY'] = 'sk-test-fake-key-never-used'
os.environ['CHAT_MODEL'] = 'test-chat-model'
os.environ['EMBEDDING_MODEL'] = 'test-embedding-model'
os.environ['DOCUMENTS_DIR'] = os.path.join(_SESSION_DIR, 'documents')
os.environ['CHROMA_DIR'] = os.path.join(_SESSION_DIR, 'chroma')
os.environ['SQLITE_PATH'] = os.path.join(_SESSION_DIR, 'app.db')


def _remove_session_dir() -> None:
    shutil.rmtree(_SESSION_DIR, ignore_errors=True)


atexit.register(_remove_session_dir)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from langchain_chroma import Chroma  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402
from pypdf import PdfWriter  # noqa: E402

from app import db  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services import document_service  # noqa: E402

# Keep the pytest output readable: the app logger owns a stream handler that
# was attached to the real stderr when `app.main` was imported.
logging.getLogger('app').setLevel(logging.WARNING)

API_DOCUMENTS = '/api/v1/documents'


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Per-test storage: catalog, PDFs and Chroma vectors inside `tmp_path`."""
    monkeypatch.setattr(settings, 'documents_dir', tmp_path / 'documents')
    monkeypatch.setattr(settings, 'chroma_dir', tmp_path / 'chroma')
    monkeypatch.setattr(settings, 'sqlite_path', tmp_path / 'app.db')
    db.init()


@pytest.fixture
def client(monkeypatch):
    """API client whose background indexing is a no-op (no real embeddings)."""
    monkeypatch.setattr(document_service, 'index_document', lambda document_id: None)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def upload(client):
    """POST `content` to the upload endpoint as multipart form data."""

    def _upload(content: bytes, filename: str = 'doc.pdf'):
        return client.post(
            API_DOCUMENTS,
            files={'file': (filename, content, 'application/pdf')},
        )

    return _upload


@pytest.fixture
def assert_error():
    """Assert the PRD §5.3 envelope `{"error": {"code", "message"}}`."""

    def _assert_error(
        response, status_code: int, code: str, message: str | None = None
    ) -> None:
        assert response.status_code == status_code
        body = response.json()
        assert set(body) == {'error'}
        assert set(body['error']) == {'code', 'message'}
        assert body['error']['code'] == code
        assert body['error']['message']
        if message is not None:
            assert body['error']['message'] == message

    return _assert_error


@pytest.fixture
def make_pdf():
    """Build a minimal valid PDF with `page_count` blank pages."""

    def _make_pdf(page_count: int = 1) -> bytes:
        writer = PdfWriter()
        for _ in range(page_count):
            writer.add_blank_page(width=200, height=200)
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    return _make_pdf


@pytest.fixture
def make_encrypted_pdf():
    """Build a password-protected PDF (RC4-40: pure Python, no extra dep)."""

    def _make_encrypted_pdf() -> bytes:
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.encrypt(user_password='secret', algorithm='RC4-40')
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    return _make_encrypted_pdf


@pytest.fixture
def insert_document():
    """Insert a catalog row in `received` directly (no upload, no indexing)."""

    def _insert_document(filename: str = 'doc.pdf') -> str:
        document_id = str(uuid.uuid4())
        db.create(
            document_id=document_id,
            filename=filename,
            storage_path=f'{document_id}.pdf',
            sha256=uuid.uuid4().hex,
            size_bytes=1024,
        )
        return document_id

    return _insert_document


@pytest.fixture
def make_ready_document(insert_document):
    """Insert a document already in `ready`, with optional page/chunk counts."""

    def _make_ready_document(
        filename: str = 'manual.pdf',
        *,
        page_count: int | None = 10,
        chunk_count: int | None = 39,
    ) -> str:
        document_id = insert_document(filename)
        db.update_status(document_id, 'processing')
        db.update_status(
            document_id, 'ready', page_count=page_count, chunk_count=chunk_count
        )
        return document_id

    return _make_ready_document


class _FakeEmbeddings(Embeddings):
    """Deterministic vectors; keeps test inserts offline (no ONNX download)."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2]


@pytest.fixture
def add_vectors():
    """Insert vectors for a document with the metadata the indexer writes.

    The fake embeddings client makes langchain embed client-side and upsert
    explicit vectors, so chromadb never calls its default ONNX model and
    nothing leaves the machine.
    """

    def _add_vectors(
        document_id: str,
        *,
        embedding_model: str | None = None,
        count: int = 2,
    ) -> list[str]:
        store = Chroma(
            collection_name=settings.chroma_collection,
            embedding_function=_FakeEmbeddings(),
            persist_directory=str(settings.chroma_dir),
            collection_metadata=document_service.CHROMA_COLLECTION_METADATA,
            client_settings=document_service.CHROMA_CLIENT_SETTINGS,
        )
        ids = [f'{document_id}:{index}' for index in range(count)]
        store.add_texts(
            texts=[f'chunk {index} content' for index in range(count)],
            metadatas=[
                {
                    'document_id': document_id,
                    'filename': 'manual.pdf',
                    'page': index + 1,
                    'chunk_index': index,
                    'embedding_model': embedding_model or settings.embedding_model,
                }
                for index in range(count)
            ],
            ids=ids,
        )
        return ids

    return _add_vectors
