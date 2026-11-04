"""The two-layer evidence rule (PRD §6.2) with a fake retriever and LLM.

`rag_service` builds the Chroma store and the structured-output LLM inside
its own functions, so the fakes replace them at exactly those points:

- `_fake_retriever` swaps `rag_service.get_vector_store` for a store that
  returns pre-scored chunks, keeping the real threshold filtering of layer 1;
- `_fake_llm` swaps `rag_service._ask_model` for a canned `AnswerOutput`.

No OpenAI call ever happens, and the assembly/citation logic under test is
entirely the production code.
"""

import pytest
from langchain_core.documents import Document as LCDocument

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.schemas.chat import ChatRequest
from app.services import rag_service
from app.services.rag_service import (
    MISSING_PARTS_PREFIX,
    NO_EVIDENCE_ANSWER,
    UNLINKED_CLAIMS_NOTICE,
    AnswerOutput,
    Claim,
)

QUESTION = 'What is the delivery deadline?'


@pytest.fixture(autouse=True)
def fixed_threshold(monkeypatch):
    """Deterministic relevance threshold, whatever `.env` configures."""
    monkeypatch.setattr(settings, 'relevance_threshold', 0.35)


class FakeVectorStore:
    """Chroma stand-in: returns pre-scored chunks and records every call."""

    def __init__(self, results):
        self._results = results
        self.calls = []

    def similarity_search_with_relevance_scores(self, question, k, filter):
        self.calls.append({'question': question, 'k': k, 'filter': filter})
        return self._results


def _chunk(text, document_id, *, page=1, filename='manual.pdf'):
    return LCDocument(
        page_content=text,
        metadata={'document_id': document_id, 'filename': filename, 'page': page},
    )


def _fake_retriever(monkeypatch, results):
    store = FakeVectorStore(results)
    monkeypatch.setattr(rag_service, 'get_vector_store', lambda: store)
    return store


def _fake_llm(monkeypatch, output=None):
    """Replace the structured LLM call; with no output, calling fails the test."""
    calls = []

    def _ask_model(question, context):
        calls.append({'question': question, 'context': context})
        if output is None:
            raise AssertionError('the LLM must not be called without evidence')
        return output

    monkeypatch.setattr(rag_service, '_ask_model', _ask_model)
    return calls


def _ask(document_id, question=QUESTION):
    return rag_service.answer_question(
        ChatRequest(question=question, document_ids=[document_id])
    )


def test_layer1_returns_fixed_answer_without_calling_the_llm(
    monkeypatch, make_ready_document
):
    document_id = make_ready_document()
    results = [
        (_chunk('chunk one content', document_id), 0.10),
        (_chunk('chunk two content', document_id), 0.20),
    ]
    store = _fake_retriever(monkeypatch, results)
    llm_calls = _fake_llm(monkeypatch)

    response = _ask(document_id)

    assert response.answer == NO_EVIDENCE_ANSWER
    assert response.has_evidence is False
    assert response.sources == []
    assert llm_calls == []
    # the search is filtered to the selected documents with RETRIEVAL_K
    assert store.calls == [
        {
            'question': QUESTION,
            'k': settings.retrieval_k,
            'filter': {'document_id': {'$in': [document_id]}},
        }
    ]


def test_layer2_model_without_evidence_returns_fixed_answer(
    monkeypatch, make_ready_document
):
    document_id = make_ready_document()
    _fake_retriever(monkeypatch, [(_chunk('chunk one content', document_id), 0.9)])
    output = AnswerOutput(claims=[], missing=[], has_evidence=False)
    llm_calls = _fake_llm(monkeypatch, output)

    response = _ask(document_id)

    assert response.answer == NO_EVIDENCE_ANSWER
    assert response.has_evidence is False
    assert response.sources == []
    assert len(llm_calls) == 1


def test_layer2_unlinked_claims_only_returns_fixed_answer(
    monkeypatch, make_ready_document
):
    document_id = make_ready_document()
    results = [
        (_chunk('chunk one content', document_id), 0.9),
        (_chunk('chunk two content', document_id), 0.9),
    ]
    _fake_retriever(monkeypatch, results)
    output = AnswerOutput(
        claims=[
            Claim(text='Claim with no citation', cited=[]),
            Claim(text='Claim citing a chunk that does not exist', cited=[99]),
            Claim(text='   ', cited=[1]),
        ],
        missing=[],
        has_evidence=True,
    )
    llm_calls = _fake_llm(monkeypatch, output)

    response = _ask(document_id)

    assert response.answer == NO_EVIDENCE_ANSWER
    assert response.has_evidence is False
    assert response.sources == []
    assert len(llm_calls) == 1


def test_valid_claims_get_sorted_deduplicated_markers(monkeypatch, make_ready_document):
    document_id = make_ready_document()
    results = [
        (_chunk('chunk one content', document_id, page=1), 0.9),
        (_chunk('chunk two content', document_id, page=2), 0.9),
        (_chunk('chunk three content', document_id, page=3), 0.9),
    ]
    _fake_retriever(monkeypatch, results)
    output = AnswerOutput(
        claims=[
            Claim(text='The deadline is 30 days', cited=[3, 1, 1]),
            Claim(text='The device turns off on its own', cited=[2]),
        ],
        missing=[],
        has_evidence=True,
    )
    _fake_llm(monkeypatch, output)

    response = _ask(document_id)

    assert response.has_evidence is True
    # markers are deduplicated, ascending and before the final punctuation, and
    # renumbered by first appearance (prompt chunks 1, 3, 2 -> [1], [2], [3])
    assert response.answer == (
        'The deadline is 30 days [1][2]. The device turns off on its own [3].'
    )
    # sources are the union of the cited chunks, in marker order
    assert [source.index for source in response.sources] == [1, 2, 3]
    assert [source.page for source in response.sources] == [1, 3, 2]
    assert all(str(source.document_id) == document_id for source in response.sources)
    assert all(source.filename == 'manual.pdf' for source in response.sources)


def test_model_markers_and_trecho_tags_are_stripped(monkeypatch, make_ready_document):
    document_id = make_ready_document()
    _fake_retriever(monkeypatch, [(_chunk('chunk one content', document_id), 0.9)])
    output = AnswerOutput(
        claims=[
            Claim(
                text='Restart <trecho> the system [2] today </trecho>.',
                cited=[1],
            )
        ],
        missing=[],
        has_evidence=True,
    )
    _fake_llm(monkeypatch, output)

    response = _ask(document_id)

    # NOTE: the production regex removes `<trecho`/`</trecho` but leaves the
    # closing `>` behind (reported as a cosmetic finding, not fixed here).
    assert response.answer == 'Restart > the system today > [1].'
    assert '<trecho' not in response.answer
    assert '</trecho' not in response.answer
    assert '[2]' not in response.answer


def test_dropped_claims_add_the_notice_paragraph(monkeypatch, make_ready_document):
    document_id = make_ready_document()
    results = [
        (_chunk('chunk one content', document_id), 0.9),
        (_chunk('chunk two content', document_id), 0.9),
    ]
    _fake_retriever(monkeypatch, results)
    output = AnswerOutput(
        claims=[
            Claim(text='Valid claim', cited=[1]),
            Claim(text='Claim with no citation', cited=[]),
            Claim(text='Claim citing a chunk that does not exist', cited=[42]),
        ],
        missing=[],
        has_evidence=True,
    )
    _fake_llm(monkeypatch, output)

    response = _ask(document_id)

    assert response.has_evidence is True
    assert response.answer == f'Valid claim [1].\n\n{UNLINKED_CLAIMS_NOTICE}'
    assert [source.index for source in response.sources] == [1]


def test_missing_parts_add_the_missing_paragraph(monkeypatch, make_ready_document):
    document_id = make_ready_document()
    _fake_retriever(monkeypatch, [(_chunk('chunk one content', document_id), 0.9)])
    output = AnswerOutput(
        claims=[Claim(text='Valid claim', cited=[1])],
        missing=['the delivery deadline ', ''],
        has_evidence=True,
    )
    _fake_llm(monkeypatch, output)

    response = _ask(document_id)

    assert response.has_evidence is True
    assert response.answer == (
        f'Valid claim [1].\n\n{MISSING_PARTS_PREFIX}the delivery deadline.'
    )


def test_excerpt_is_truncated_to_the_configured_limit(monkeypatch, make_ready_document):
    document_id = make_ready_document()
    monkeypatch.setattr(settings, 'excerpt_max_chars', 10)
    _fake_retriever(monkeypatch, [(_chunk('x' * 40, document_id), 0.9)])
    output = AnswerOutput(
        claims=[Claim(text='Valid claim', cited=[1])],
        missing=[],
        has_evidence=True,
    )
    _fake_llm(monkeypatch, output)

    response = _ask(document_id)

    assert len(response.sources) == 1
    assert response.sources[0].excerpt == 'x' * 10


def test_sources_list_only_cited_chunks(monkeypatch, make_ready_document):
    document_id = make_ready_document()
    results = [
        (_chunk('chunk one content', document_id, page=1), 0.9),
        (_chunk('chunk two content', document_id, page=2), 0.9),
        (_chunk('chunk three content', document_id, page=3), 0.9),
    ]
    _fake_retriever(monkeypatch, results)
    output = AnswerOutput(
        claims=[Claim(text='Valid claim', cited=[2])],
        missing=[],
        has_evidence=True,
    )
    _fake_llm(monkeypatch, output)

    response = _ask(document_id)

    # the only cited chunk (prompt chunk 2) is shown as [1]
    assert response.answer == 'Valid claim [1].'
    assert [source.index for source in response.sources] == [1]
    assert response.sources[0].page == 2
    assert response.sources[0].excerpt == 'chunk two content'


def _numbered_chunks(document_id, count):
    return [
        (_chunk(f'chunk {n} content', document_id, page=n), 0.9)
        for n in range(1, count + 1)
    ]


def test_single_source_cited_as_chunk_4_is_shown_as_1(monkeypatch, make_ready_document):
    document_id = make_ready_document()
    _fake_retriever(monkeypatch, _numbered_chunks(document_id, 5))
    output = AnswerOutput(
        claims=[Claim(text='The plate is ABC1D23', cited=[4])],
        missing=[],
        has_evidence=True,
    )
    _fake_llm(monkeypatch, output)

    response = _ask(document_id)

    assert response.answer == 'The plate is ABC1D23 [1].'
    assert [source.index for source in response.sources] == [1]
    assert response.sources[0].page == 4
    assert response.sources[0].excerpt == 'chunk 4 content'


def test_out_of_order_citations_are_renumbered_by_first_appearance(
    monkeypatch, make_ready_document
):
    document_id = make_ready_document()
    _fake_retriever(monkeypatch, _numbered_chunks(document_id, 6))
    output = AnswerOutput(
        claims=[
            Claim(text='First claim', cited=[5]),
            Claim(text='Second claim', cited=[6, 2]),
            Claim(text='Third claim', cited=[3, 5]),
        ],
        missing=[],
        has_evidence=True,
    )
    _fake_llm(monkeypatch, output)

    response = _ask(document_id)

    # prompt chunks 5, 2, 6, 3 -> [1], [2], [3], [4]; markers stay ascending
    assert response.answer == (
        'First claim [1]. Second claim [2][3]. Third claim [1][4].'
    )
    assert [source.index for source in response.sources] == [1, 2, 3, 4]
    assert [source.page for source in response.sources] == [5, 2, 6, 3]


def test_chunk_cited_twice_keeps_a_single_number(monkeypatch, make_ready_document):
    document_id = make_ready_document()
    _fake_retriever(monkeypatch, _numbered_chunks(document_id, 4))
    output = AnswerOutput(
        claims=[
            Claim(text='First claim', cited=[3]),
            Claim(text='Second claim', cited=[3, 3]),
        ],
        missing=[],
        has_evidence=True,
    )
    _fake_llm(monkeypatch, output)

    response = _ask(document_id)

    assert response.answer == 'First claim [1]. Second claim [1].'
    assert [source.index for source in response.sources] == [1]
    assert response.sources[0].page == 3


def test_document_not_ready_returns_document_not_ready(insert_document):
    document_id = insert_document()  # status: received

    with pytest.raises(AppError) as exc_info:
        _ask(document_id)

    assert exc_info.value.code == ErrorCode.DOCUMENT_NOT_READY
    assert exc_info.value.status_code == 409
