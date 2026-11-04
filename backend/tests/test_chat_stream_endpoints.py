"""`/chat/query/stream` endpoint (PRD §12.6, task 7.13).

The streaming path fakes the model exactly at the call point
(`rag_service._stream_model`) and the retriever at
`rag_service.get_vector_store`; everything else — validation, layer 1,
marker filtering, SSE rendering and error envelopes — is production code.
"""

import json
import re
import uuid

import pytest
from langchain_core.documents import Document as LCDocument

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.services import rag_service
from app.services.rag_service import NO_EVIDENCE_ANSWER

API_STREAM = '/api/v1/chat/query/stream'
QUESTION = 'What is the restart procedure?'
MARKER_PATTERN = re.compile(r'\[\d+\]')
PROVIDER_ERROR_MESSAGE = 'O serviço de IA não respondeu corretamente. Tente novamente.'


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


def _fake_stream_model(monkeypatch, pieces):
    """Replace the streaming model call with fixed text pieces."""
    calls = []

    def _stream_model(question, context):
        calls.append({'question': question, 'context': context})
        yield from pieces

    monkeypatch.setattr(rag_service, '_stream_model', _stream_model)
    return calls


def _forbidden_stream_model(monkeypatch):
    """Fail the test if the streaming path ever calls the model."""

    def _stream_model(question, context):
        raise AssertionError('the model must not be called without evidence')

    monkeypatch.setattr(rag_service, '_stream_model', _stream_model)


def _sse_events(response):
    """Parse an SSE body into its `data: {json}` event dicts."""
    events = []
    for block in response.text.split('\n\n'):
        if not block:
            continue
        assert block.startswith('data: ')
        events.append(json.loads(block[len('data: ') :]))
    return events


def _payload(document_id, **overrides):
    payload = {'question': QUESTION, 'document_ids': [str(document_id)]}
    payload.update(overrides)
    return payload


@pytest.mark.parametrize('show_sources', [None, False])
def test_stream_omitting_show_sources_answers_without_sources(
    client, monkeypatch, make_ready_document, show_sources
):
    document_id = make_ready_document()
    _fake_retriever(monkeypatch, [(_chunk('chunk one content', document_id), 0.9)])
    # the pieces carry a whole marker, a marker split across pieces and a
    # literal bracket that must survive
    pieces = [
        'Desligue o equipamento [3] e aguarde 30 segundos.',
        ' Depois, mantenha [',
        '1, 2] o botão por [anexo] 5 segundos.',
    ]
    calls = _fake_stream_model(monkeypatch, pieces)
    overrides = {} if show_sources is None else {'show_sources': show_sources}

    response = client.post(API_STREAM, json=_payload(document_id, **overrides))

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/event-stream')
    assert response.headers['cache-control'] == 'no-cache'
    events = _sse_events(response)
    deltas = [event for event in events if event['type'] == 'delta']
    # exactly one done event, and it closes a successful stream
    assert events[-1] == {'type': 'done', 'has_evidence': True}
    assert [event['type'] for event in events].count('done') == 1
    assert deltas
    assert all(set(delta) == {'type', 'text'} for delta in deltas)
    answer = ''.join(delta['text'] for delta in deltas)
    # model markers never reach the client; literal brackets do
    assert MARKER_PATTERN.search(answer) is None
    assert answer == (
        'Desligue o equipamento e aguarde 30 segundos. '
        'Depois, mantenha o botão por [anexo] 5 segundos.'
    )
    # the model was streamed exactly once, for this question
    assert [call['question'] for call in calls] == [QUESTION]


def test_stream_with_explicit_show_sources_true_returns_422(client, assert_error):
    response = client.post(API_STREAM, json=_payload(uuid.uuid4(), show_sources=True))

    # a pre-stream error is a JSON envelope, never an SSE body
    assert_error(
        response,
        422,
        'stream_sources_unsupported',
        'O endpoint de streaming não exibe fontes; use /chat/query.',
    )
    assert response.headers['content-type'].startswith('application/json')
    assert not response.text.startswith('data: ')


def test_stream_with_not_ready_document_returns_409_json(
    client, insert_document, assert_error
):
    document_id = insert_document()  # status: received

    response = client.post(API_STREAM, json=_payload(document_id))

    # raised before the stream starts: JSON with the right status
    assert_error(
        response,
        409,
        'document_not_ready',
        'Um ou mais documentos selecionados não estão prontos.',
    )
    assert response.headers['content-type'].startswith('application/json')
    assert not response.text.startswith('data: ')


def test_stream_provider_failure_keeps_partial_and_ends_with_error_event(
    client, monkeypatch, make_ready_document
):
    document_id = make_ready_document()
    _fake_retriever(monkeypatch, [(_chunk('chunk one content', document_id), 0.9)])

    def _stream_model(question, context):
        yield 'First part'
        raise AppError(ErrorCode.PROVIDER_ERROR)

    monkeypatch.setattr(rag_service, '_stream_model', _stream_model)

    response = client.post(API_STREAM, json=_payload(document_id))

    # the 200 is already committed: the failure becomes a final error event
    assert response.status_code == 200
    events = _sse_events(response)
    assert events[0] == {'type': 'delta', 'text': 'First part'}
    assert events[-1] == {
        'type': 'error',
        'error': {'code': 'provider_error', 'message': PROVIDER_ERROR_MESSAGE},
    }
    # the partial stays and no done event follows a failed generation
    assert [event['type'] for event in events] == ['delta', 'error']


def test_stream_layer1_single_delta_with_fixed_answer_and_no_model_call(
    client, monkeypatch, make_ready_document
):
    document_id = make_ready_document()
    results = [
        (_chunk('chunk one content', document_id), 0.10),
        (_chunk('chunk two content', document_id), 0.20),
    ]
    _fake_retriever(monkeypatch, results)
    _forbidden_stream_model(monkeypatch)

    response = client.post(API_STREAM, json=_payload(document_id))

    assert response.status_code == 200
    assert _sse_events(response) == [
        {'type': 'delta', 'text': NO_EVIDENCE_ANSWER},
        {'type': 'done', 'has_evidence': False},
    ]
