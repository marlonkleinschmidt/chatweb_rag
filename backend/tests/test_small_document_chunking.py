"""Task 7.33: a small 1-page document is indexed as a single chunk.

Exercises `document_service._split` directly with LangChain page documents
(the shape `_load_pages` returns, with 1-based `page`), so no PDF parsing,
embedding or Chroma call is involved.
"""

import pytest
from langchain_core.documents import Document as LCDocument

from app.core.config import settings
from app.services import document_service

DOCUMENT_ID = '00000000-0000-0000-0000-000000000001'
FILENAME = 'form.pdf'
CHUNK_SIZE = 100
CHUNK_OVERLAP = 20
METADATA_KEYS = {
    'document_id',
    'filename',
    'page',
    'chunk_index',
    'embedding_model',
    'created_at',
    'updated_at',
}


def _text(length: int) -> str:
    """Splittable text of exactly `length` characters (words of 9 + space)."""
    return ('abcdefghi ' * (length // 10 + 1))[:length]


def _pages(*lengths: int) -> list[LCDocument]:
    return [
        LCDocument(page_content=_text(length), metadata={'page': number})
        for number, length in enumerate(lengths, start=1)
    ]


@pytest.fixture(autouse=True)
def _small_chunks(monkeypatch):
    monkeypatch.setattr(settings, 'chunk_size', CHUNK_SIZE)
    monkeypatch.setattr(settings, 'chunk_overlap', CHUNK_OVERLAP)
    monkeypatch.setattr(settings, 'small_document_max_chars', 1000)


def test_small_single_page_document_becomes_one_chunk():
    pages = _pages(800)

    chunks = document_service._split(DOCUMENT_ID, FILENAME, pages)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.page_content == pages[0].page_content
    assert set(chunk.metadata) == METADATA_KEYS
    assert chunk.metadata['page'] == 1
    assert chunk.metadata['chunk_index'] == 0
    assert chunk.metadata['document_id'] == DOCUMENT_ID
    assert chunk.metadata['filename'] == FILENAME


def test_limit_is_inclusive():
    chunks = document_service._split(DOCUMENT_ID, FILENAME, _pages(1000))

    assert len(chunks) == 1


def test_single_page_above_limit_uses_the_splitter():
    chunks = document_service._split(DOCUMENT_ID, FILENAME, _pages(1001))

    assert len(chunks) > 1
    assert all(len(chunk.page_content) <= CHUNK_SIZE for chunk in chunks)
    assert [chunk.metadata['chunk_index'] for chunk in chunks] == list(
        range(len(chunks))
    )
    assert {chunk.metadata['page'] for chunk in chunks} == {1}


def test_multi_page_document_is_never_merged():
    # Two short pages fit the limit together, but one chunk could only cite
    # one page, so the normal per-page splitting applies.
    pages = _pages(80, 90)

    chunks = document_service._split(DOCUMENT_ID, FILENAME, pages)

    assert [chunk.metadata['page'] for chunk in chunks] == [1, 2]
    assert [chunk.page_content for chunk in chunks] == [
        page.page_content.strip() for page in pages
    ]


def test_limit_is_configurable(monkeypatch):
    pages = _pages(800)

    monkeypatch.setattr(settings, 'small_document_max_chars', 500)
    assert len(document_service._split(DOCUMENT_ID, FILENAME, pages)) > 1

    monkeypatch.setattr(settings, 'small_document_max_chars', 800)
    assert len(document_service._split(DOCUMENT_ID, FILENAME, pages)) == 1


def test_zero_disables_the_rule(monkeypatch):
    monkeypatch.setattr(settings, 'small_document_max_chars', 0)

    chunks = document_service._split(DOCUMENT_ID, FILENAME, _pages(300))

    assert len(chunks) > 1


def test_default_limit_comes_from_the_settings_class():
    assert type(settings).model_fields['small_document_max_chars'].default == 4000
