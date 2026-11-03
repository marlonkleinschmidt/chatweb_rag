"""Question answering over the selected documents (PRD §6.2)."""

import html
import logging
import re
import time
from typing import Any

from langchain_core.documents import Document as LCDocument
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app import db
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.schemas.chat import ChatRequest, ChatResponse, Source
from app.services.document_service import get_vector_store, provider_error_code
from app.services.prompts import ANSWER_PROMPT_V1, QUESTION_PROMPT_V1

logger = logging.getLogger(__name__)

# RF-14: fixed answer whenever the evidence rule fails.
NO_EVIDENCE_ANSWER = (
    'Não encontrei evidências suficientes nos documentos selecionados para '
    'responder a essa pergunta.'
)
READY_STATUS = 'ready'
# One retry on provider calls (PRD §6.2).
PROVIDER_MAX_RETRIES = 1
# Matches `<trecho` and `</trecho` in any case, so chunk text cannot open or close
# a context block (prompt injection defence, PRD §6.3).
TRECHO_TAG_PATTERN = re.compile(r'</?trecho', re.IGNORECASE)

_PROMPT = ChatPromptTemplate.from_messages(
    [('system', ANSWER_PROMPT_V1), ('human', QUESTION_PROMPT_V1)]
)


class AnswerOutput(BaseModel):
    # Structured output schema from PRD §6.2 step 6. No docstring or field
    # descriptions: they would be sent to the model on top of the prompt.
    has_evidence: bool
    answer: str
    cited: list[int]


def _no_evidence() -> ChatResponse:
    return ChatResponse(answer=NO_EVIDENCE_ANSWER, has_evidence=False, sources=[])


def _ensure_ready(document_ids: list[str]) -> None:
    """Step 1: every document must exist and be `ready`, else `409`."""
    for document_id in document_ids:
        row = db.get(document_id)
        if row is None or row['status'] != READY_STATUS:
            raise AppError(ErrorCode.DOCUMENT_NOT_READY)


def _ensure_provider_configured() -> None:
    """Missing key or model names fail safely as `502 provider_error`."""
    if (
        settings.openai_api_key is None
        or not settings.chat_model
        or not settings.embedding_model
    ):
        logger.error(
            'provider_not_configured error_code=%s', ErrorCode.PROVIDER_ERROR.value
        )
        raise AppError(ErrorCode.PROVIDER_ERROR)


def _provider_failure(exc: Exception, stage: str) -> AppError:
    """Map a provider exception to `provider_timeout` (504) or `provider_error`."""
    code = provider_error_code(exc) or ErrorCode.PROVIDER_ERROR
    logger.warning(
        'query_provider_failed stage=%s error_code=%s exc_type=%s',
        stage,
        code.value,
        type(exc).__name__,
    )
    return AppError(code)


def _retrieve(question: str, document_ids: list[str]) -> list[LCDocument]:
    """Steps 2-3: top `RETRIEVAL_K` chunks of the selected documents, filtered by
    `RELEVANCE_THRESHOLD`, most relevant first."""
    store = get_vector_store()
    try:
        results = store.similarity_search_with_relevance_scores(
            question,
            k=settings.retrieval_k,
            filter={'document_id': {'$in': document_ids}},
        )
    except Exception as exc:
        if provider_error_code(exc) is None:
            raise
        raise _provider_failure(exc, 'retrieval') from exc
    return [doc for doc, score in results if score >= settings.relevance_threshold]


def _clean_chunk_text(text: str) -> str:
    """Remove `<trecho`/`</trecho` until none is left (removal may form new ones)."""
    while TRECHO_TAG_PATTERN.search(text):
        text = TRECHO_TAG_PATTERN.sub('', text)
    return text


def _page(metadata: dict[str, Any]) -> int | None:
    """1-based page from chunk metadata, or None when absent or invalid."""
    page = metadata.get('page')
    if isinstance(page, int) and not isinstance(page, bool) and page >= 1:
        return page
    return None


def _build_context(chunks: list[LCDocument]) -> str:
    """Step 5: number chunks 1..n in the PRD §6.3 `<trecho>` format."""
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        filename = html.escape(str(chunk.metadata.get('filename', '')), quote=True)
        page = _page(chunk.metadata)
        blocks.append(
            f'<trecho id="{index}" arquivo="{filename}" '
            f'pagina="{page if page is not None else ""}">\n'
            f'{_clean_chunk_text(chunk.page_content).strip()}\n'
            '</trecho>'
        )
    return '\n\n'.join(blocks)


def _ask_model(question: str, context: str) -> AnswerOutput | None:
    """Step 6: call the chat model with structured output."""
    model = ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.openai_api_key,
        temperature=settings.chat_temperature,
        timeout=settings.provider_timeout_s,
        max_retries=PROVIDER_MAX_RETRIES,
    )
    chain = _PROMPT | model.with_structured_output(AnswerOutput, method='json_schema')
    try:
        result = chain.invoke({'context': context, 'question': question})
    except Exception as exc:
        # Includes unparsable or refused structured output: the provider did not
        # answer correctly.
        raise _provider_failure(exc, 'generation') from exc
    return result if isinstance(result, AnswerOutput) else None


def _validated_citations(output: AnswerOutput | None, chunk_count: int) -> list[int]:
    """Step 7: cited indices in ascending order, or [] when evidence is missing."""
    if output is None or not output.has_evidence or not output.answer.strip():
        return []
    if not output.cited:
        return []
    if any(index < 1 or index > chunk_count for index in output.cited):
        return []
    return sorted(set(output.cited))


def _source(index: int, chunk: LCDocument) -> Source:
    """Step 8: public source for chunk `[index]`, with a truncated excerpt."""
    return Source(
        index=index,
        document_id=chunk.metadata['document_id'],
        filename=str(chunk.metadata.get('filename', '')),
        page=_page(chunk.metadata),
        excerpt=chunk.page_content.strip()[: settings.excerpt_max_chars],
    )


def _log_query(
    started: float,
    document_ids: list[str],
    chunk_count: int,
    output: AnswerOutput | None,
    cited: list[int],
) -> None:
    """Log only IDs, counts, flags and duration (never question or answer)."""
    logger.info(
        'query_done document_ids=%s chunk_count=%d llm_called=%s '
        'model_has_evidence=%s has_evidence=%s cited_count=%d duration_ms=%d',
        ','.join(document_ids),
        chunk_count,
        chunk_count > 0,
        output.has_evidence if output is not None else None,
        bool(cited),
        len(cited),
        (time.monotonic() - started) * 1000,
    )


def answer_question(request: ChatRequest) -> ChatResponse:
    """Answer one independent question using only the selected documents.

    Applies the two-layer evidence rule (PRD §6.2); when it fails, returns the
    fixed RF-14 answer with `has_evidence=False` and no sources.

    Raises `AppError` with:
    - `document_not_ready` (409): a document does not exist or is not `ready`;
    - `provider_error` (502): OpenAI not configured, failed or gave an invalid
      structured answer;
    - `provider_timeout` (504): OpenAI timed out (after one retry).
    """
    started = time.monotonic()
    document_ids = list(dict.fromkeys(str(item) for item in request.document_ids))
    _ensure_ready(document_ids)
    _ensure_provider_configured()

    chunks = _retrieve(request.question, document_ids)
    if not chunks:
        # Layer 1: nothing relevant enough, so the model is not called.
        _log_query(started, document_ids, 0, None, [])
        return _no_evidence()

    output = _ask_model(request.question, _build_context(chunks))
    cited = _validated_citations(output, len(chunks))
    _log_query(started, document_ids, len(chunks), output, cited)
    if not cited:
        # Layer 2: the model reported no evidence or cited invalid chunks.
        return _no_evidence()

    assert output is not None
    return ChatResponse(
        answer=output.answer.strip(),
        has_evidence=True,
        sources=[_source(index, chunks[index - 1]) for index in cited],
    )
