"""`/chat/query` without sources (PRD §12.6, task 7.13).

Same fake pattern as `test_evidence_rule.py`: the retriever is swapped at
`rag_service.get_vector_store` (pre-scored chunks, real layer-1 threshold)
and the structured LLM at `rag_service._ask_model`. Requests go through the
HTTP endpoint so `show_sources` crosses the real contract.
"""

import re

import pytest
from langchain_core.documents import Document as LCDocument

from app.core.config import settings
from app.services import rag_service
from app.services.rag_service import (
    MISSING_PARTS_PREFIX,
    NO_EVIDENCE_ANSWER,
    UNLINKED_CLAIMS_NOTICE,
    AnswerOutput,
    Claim,
)

API_CHAT = '/api/v1/chat/query'
QUESTION = 'What is the delivery deadline?'
MARKER_PATTERN = re.compile(r'\[\d+\]')


@pytest.fixture(autouse=True)
def fixed_threshold(monkeypatch):
    """Deterministic relevance threshold, whatever `.env` configures."""
    monkeypatch.setattr(settings, 'relevance_threshold', 0.35)


class FakeVectorStore:
    """Chroma stand-in: returns pre-scored chunks."""

    def __init__(self, results):
        self._results = results

    def similarity_search_with_relevance_scores(self, question, k, filter):
        return self._results


def _chunk(text, document_id, *, page=1):
    return LCDocument(
        page_content=text,
        metadata={'document_id': document_id, 'filename': 'manual.pdf', 'page': page},
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


def _payload(document_id, **overrides):
    payload = {'question': QUESTION, 'document_ids': [str(document_id)]}
    payload.update(overrides)
    return payload


def test_without_sources_valid_claims_become_plain_sentences(
    client, monkeypatch, make_ready_document
):
    document_id = make_ready_document()
    _fake_retriever(
        monkeypatch,
        [
            (_chunk('chunk one content', document_id, page=1), 0.9),
            (_chunk('chunk two content', document_id, page=2), 0.9),
        ],
    )
    output = AnswerOutput(
        claims=[
            # no final punctuation: the plain sentence adds its own period
            Claim(text='The deadline is 30 days', cited=[2, 1, 1]),
            # already punctuated: kept as written
            Claim(text='The device turns off on its own.', cited=[1]),
            Claim(text='Claim with no citation', cited=[]),
        ],
        missing=['the warranty period'],
        has_evidence=True,
    )
    _fake_llm(monkeypatch, output)

    response = client.post(API_CHAT, json=_payload(document_id, show_sources=False))

    assert response.status_code == 200
    body = response.json()
    assert body['has_evidence'] is True
    assert body['sources'] == []
    assert MARKER_PATTERN.search(body['answer']) is None
    # plain sentences without markers; the fixed paragraphs are kept
    assert body['answer'] == (
        'The deadline is 30 days. The device turns off on its own.'
        f'\n\n{MISSING_PARTS_PREFIX}the warranty period.'
        f'\n\n{UNLINKED_CLAIMS_NOTICE}'
    )


def test_without_sources_model_markers_are_stripped_from_claims(
    client, monkeypatch, make_ready_document
):
    document_id = make_ready_document()
    _fake_retriever(monkeypatch, [(_chunk('chunk one content', document_id), 0.9)])
    output = AnswerOutput(
        claims=[Claim(text='Restart [2] the system today', cited=[1])],
        missing=[],
        has_evidence=True,
    )
    _fake_llm(monkeypatch, output)

    response = client.post(API_CHAT, json=_payload(document_id, show_sources=False))

    assert response.status_code == 200
    body = response.json()
    assert body['answer'] == 'Restart the system today.'
    assert MARKER_PATTERN.search(body['answer']) is None


def test_without_sources_layer1_returns_fixed_answer_without_calling_the_llm(
    client, monkeypatch, make_ready_document
):
    document_id = make_ready_document()
    results = [
        (_chunk('chunk one content', document_id), 0.10),
        (_chunk('chunk two content', document_id), 0.20),
    ]
    _fake_retriever(monkeypatch, results)
    llm_calls = _fake_llm(monkeypatch)

    response = client.post(API_CHAT, json=_payload(document_id, show_sources=False))

    assert response.status_code == 200
    body = response.json()
    assert body == {'answer': NO_EVIDENCE_ANSWER, 'has_evidence': False, 'sources': []}
    assert llm_calls == []


def test_without_sources_layer2_model_without_evidence_returns_fixed_answer(
    client, monkeypatch, make_ready_document
):
    document_id = make_ready_document()
    _fake_retriever(monkeypatch, [(_chunk('chunk one content', document_id), 0.9)])
    output = AnswerOutput(claims=[], missing=[], has_evidence=False)
    llm_calls = _fake_llm(monkeypatch, output)

    response = client.post(API_CHAT, json=_payload(document_id, show_sources=False))

    assert response.status_code == 200
    body = response.json()
    assert body == {'answer': NO_EVIDENCE_ANSWER, 'has_evidence': False, 'sources': []}
    assert len(llm_calls) == 1


def test_without_sources_layer2_unlinked_claims_only_returns_fixed_answer(
    client, monkeypatch, make_ready_document
):
    document_id = make_ready_document()
    _fake_retriever(monkeypatch, [(_chunk('chunk one content', document_id), 0.9)])
    output = AnswerOutput(
        claims=[
            Claim(text='Claim with no citation', cited=[]),
            Claim(text='Claim citing a chunk that does not exist', cited=[99]),
        ],
        missing=[],
        has_evidence=True,
    )
    llm_calls = _fake_llm(monkeypatch, output)

    response = client.post(API_CHAT, json=_payload(document_id, show_sources=False))

    assert response.status_code == 200
    body = response.json()
    assert body == {'answer': NO_EVIDENCE_ANSWER, 'has_evidence': False, 'sources': []}
    assert len(llm_calls) == 1


@pytest.mark.parametrize('show_sources', [None, True])
def test_with_sources_keeps_today_s_behavior(
    client, monkeypatch, make_ready_document, show_sources
):
    # Contrast (PRD §12.6): omitted `show_sources` defaults to `true`, and an
    # explicit `true` behaves exactly like the pre-feature endpoint.
    document_id = make_ready_document()
    _fake_retriever(
        monkeypatch,
        [
            (_chunk('chunk one content', document_id, page=1), 0.9),
            (_chunk('chunk two content', document_id, page=2), 0.9),
        ],
    )
    output = AnswerOutput(
        claims=[Claim(text='The deadline is 30 days', cited=[2, 1, 1])],
        missing=[],
        has_evidence=True,
    )
    _fake_llm(monkeypatch, output)
    overrides = {} if show_sources is None else {'show_sources': show_sources}

    response = client.post(API_CHAT, json=_payload(document_id, **overrides))

    assert response.status_code == 200
    body = response.json()
    assert body['has_evidence'] is True
    assert body['answer'] == 'The deadline is 30 days [1][2].'
    assert [source['index'] for source in body['sources']] == [1, 2]
