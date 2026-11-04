"""Per-document retrieval quota with 2+ selected documents (task 7.29).

A fake vector store holds pre-scored chunks and applies the same filters
Chroma would (`{'document_id': {'$in': ids}}` and `{'document_id': id}`),
returning the top `k` by score. The threshold filtering, the quota and the
merge are the production code of `rag_service._retrieve`.
"""

import pytest
from langchain_core.documents import Document as LCDocument

from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatStreamRequest
from app.services import rag_service
from app.services.rag_service import NO_EVIDENCE_ANSWER, AnswerOutput, Claim

QUESTION = 'Qual é a placa do veículo e como reiniciar o celular?'
BIG = 'doc-big'
SMALL = 'doc-small'
THIRD = 'doc-third'


@pytest.fixture(autouse=True)
def fixed_settings(monkeypatch):
    """Deterministic retrieval settings, whatever `.env` configures."""
    monkeypatch.setattr(settings, 'retrieval_k', 8)
    monkeypatch.setattr(settings, 'relevance_threshold', 0.35)
    monkeypatch.setattr(settings, 'min_chunks_per_document', 1)


class FilteringVectorStore:
    """Chroma stand-in that applies `document_id` filters and the top-k cut."""

    def __init__(self, scored_chunks):
        self._scored = sorted(scored_chunks, key=lambda item: item[1], reverse=True)
        self.calls = []

    def similarity_search_with_relevance_scores(self, question, k, filter):
        self.calls.append({'question': question, 'k': k, 'filter': filter})
        condition = filter['document_id']
        if isinstance(condition, dict):
            allowed = set(condition['$in'])
        else:
            allowed = {condition}
        matches = [
            item for item in self._scored if item[0].metadata['document_id'] in allowed
        ]
        return matches[:k]


def _chunk(document_id, index, score):
    doc = LCDocument(
        page_content=f'{document_id} chunk {index}',
        metadata={
            'document_id': document_id,
            'filename': f'{document_id}.pdf',
            'page': index + 1,
            'chunk_index': index,
        },
    )
    return doc, score


def _store(monkeypatch, scored_chunks):
    store = FilteringVectorStore(scored_chunks)
    monkeypatch.setattr(rag_service, 'get_vector_store', lambda: store)
    return store


def _keys(chunks):
    return [(c.metadata['document_id'], c.metadata['chunk_index']) for c in chunks]


def _big_document(count=20, top=0.80):
    """A large document whose chunks all score above the small one's."""
    return [_chunk(BIG, index, top - index * 0.005) for index in range(count)]


def test_small_document_above_threshold_enters_when_big_one_dominates(monkeypatch):
    _store(monkeypatch, _big_document() + [_chunk(SMALL, 0, 0.50)])

    chunks = rag_service._retrieve(QUESTION, [BIG, SMALL])

    keys = _keys(chunks)
    assert (SMALL, 0) in keys
    assert len(chunks) == settings.retrieval_k
    # the small chunk takes the last global slot and the order stays by score
    assert keys[:-1] == [(BIG, index) for index in range(7)]
    assert keys[-1] == (SMALL, 0)


def test_chunk_below_threshold_does_not_enter_through_the_quota(monkeypatch):
    _store(monkeypatch, _big_document() + [_chunk(SMALL, 0, 0.34)])

    chunks = rag_service._retrieve(QUESTION, [BIG, SMALL])

    assert _keys(chunks) == [(BIG, index) for index in range(8)]


def test_single_document_keeps_the_previous_behaviour(monkeypatch):
    store = _store(monkeypatch, _big_document() + [_chunk(SMALL, 0, 0.99)])

    chunks = rag_service._retrieve(QUESTION, [BIG])

    assert _keys(chunks) == [(BIG, index) for index in range(8)]
    # only the global search runs, exactly as before task 7.29
    assert store.calls == [
        {
            'question': QUESTION,
            'k': settings.retrieval_k,
            'filter': {'document_id': {'$in': [BIG]}},
        }
    ]


def test_quota_zero_disables_the_per_document_search(monkeypatch):
    monkeypatch.setattr(settings, 'min_chunks_per_document', 0)
    store = _store(monkeypatch, _big_document() + [_chunk(SMALL, 0, 0.50)])

    chunks = rag_service._retrieve(QUESTION, [BIG, SMALL])

    assert _keys(chunks) == [(BIG, index) for index in range(8)]
    assert len(store.calls) == 1


def test_per_document_searches_use_the_quota_and_the_document_filter(monkeypatch):
    monkeypatch.setattr(settings, 'min_chunks_per_document', 2)
    store = _store(monkeypatch, _big_document() + [_chunk(SMALL, 0, 0.50)])

    rag_service._retrieve(QUESTION, [BIG, SMALL])

    # the searches run concurrently, so their order is not fixed
    expected = [
        {
            'question': QUESTION,
            'k': 8,
            'filter': {'document_id': {'$in': [BIG, SMALL]}},
        },
        {'question': QUESTION, 'k': 2, 'filter': {'document_id': BIG}},
        {'question': QUESTION, 'k': 2, 'filter': {'document_id': SMALL}},
    ]
    assert len(store.calls) == len(expected)
    assert all(call in store.calls for call in expected)


@pytest.mark.parametrize('quota', [1, 2, 3])
def test_total_never_exceeds_retrieval_k_and_has_no_duplicates(monkeypatch, quota):
    monkeypatch.setattr(settings, 'min_chunks_per_document', quota)
    small = [_chunk(SMALL, index, 0.60 - index * 0.01) for index in range(5)]
    third = [_chunk(THIRD, index, 0.45 - index * 0.01) for index in range(5)]
    _store(monkeypatch, _big_document() + small + third)

    chunks = rag_service._retrieve(QUESTION, [BIG, SMALL, THIRD])

    keys = _keys(chunks)
    assert len(chunks) <= settings.retrieval_k
    assert len(keys) == len(set(keys))
    # every document keeps its quota while the reservations fit in K; past
    # that (3 x 3 > 8) each still keeps at least one chunk
    expected = quota if quota * 3 <= settings.retrieval_k else 1
    for document_id in (BIG, SMALL, THIRD):
        assert sum(key[0] == document_id for key in keys) >= expected
    # most relevant first
    by_key = {
        (doc.metadata['document_id'], doc.metadata['chunk_index']): score
        for doc, score in _big_document() + small + third
    }
    ordered = [by_key[key] for key in keys]
    assert ordered == sorted(ordered, reverse=True)


def test_reservations_beyond_retrieval_k_keep_one_chunk_per_document(monkeypatch):
    monkeypatch.setattr(settings, 'retrieval_k', 3)
    monkeypatch.setattr(settings, 'min_chunks_per_document', 2)
    scored = []
    for position, document_id in enumerate((BIG, SMALL, THIRD)):
        top = 0.90 - position * 0.10
        scored += [_chunk(document_id, index, top - index * 0.01) for index in range(3)]
    _store(monkeypatch, scored)

    chunks = rag_service._retrieve(QUESTION, [BIG, SMALL, THIRD])

    assert _keys(chunks) == [(BIG, 0), (SMALL, 0), (THIRD, 0)]


def test_layer1_still_skips_the_llm_with_several_documents(
    monkeypatch, make_ready_document
):
    big_id = make_ready_document()
    small_id = make_ready_document()
    _store(
        monkeypatch,
        [_chunk(big_id, 0, 0.20), _chunk(small_id, 0, 0.30)],
    )

    def _ask_model(question, context):
        raise AssertionError('the LLM must not be called without evidence')

    monkeypatch.setattr(rag_service, '_ask_model', _ask_model)

    response = rag_service.answer_question(
        ChatRequest(question=QUESTION, document_ids=[big_id, small_id])
    )

    assert response.answer == NO_EVIDENCE_ANSWER
    assert response.has_evidence is False


def test_quota_chunk_reaches_the_prompt_and_the_sources(
    monkeypatch, make_ready_document
):
    big_id = make_ready_document()
    small_id = make_ready_document()
    scored = [_chunk(big_id, index, 0.80 - index * 0.005) for index in range(20)]
    _store(monkeypatch, scored + [_chunk(small_id, 0, 0.50)])
    contexts = []

    def _ask_model(question, context):
        contexts.append(context)
        # the small document's chunk is the last one (lowest score): [8]
        return AnswerOutput(
            claims=[Claim(text='A placa está no documento.', cited=[8])],
            missing=[],
            has_evidence=True,
        )

    monkeypatch.setattr(rag_service, '_ask_model', _ask_model)

    response = rag_service.answer_question(
        ChatRequest(question=QUESTION, document_ids=[big_id, small_id])
    )

    assert f'{small_id} chunk 0' in contexts[0]
    assert [str(source.document_id) for source in response.sources] == [small_id]


def test_streaming_uses_the_same_retrieval(monkeypatch, make_ready_document):
    big_id = make_ready_document()
    small_id = make_ready_document()
    scored = [_chunk(big_id, index, 0.80 - index * 0.005) for index in range(20)]
    _store(monkeypatch, scored + [_chunk(small_id, 0, 0.50)])
    contexts = []

    def _stream_model(question, context):
        contexts.append(context)
        yield 'Resposta.'

    monkeypatch.setattr(rag_service, '_stream_model', _stream_model)

    events = list(
        rag_service.stream_answer(
            ChatStreamRequest(question=QUESTION, document_ids=[big_id, small_id])
        )
    )

    assert events[-1] == {'type': 'done', 'has_evidence': True}
    assert f'{small_id} chunk 0' in contexts[0]
