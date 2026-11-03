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
from app.services.prompts import ANSWER_PROMPT_V2, QUESTION_PROMPT_V1

logger = logging.getLogger(__name__)

# RF-14: fixed answer whenever the evidence rule fails.
NO_EVIDENCE_ANSWER = (
    'Não encontrei evidências suficientes nos documentos selecionados para '
    'responder a essa pergunta.'
)
# Fixed texts added to an answer with evidence (PRD §6.2, step 8).
MISSING_PARTS_PREFIX = 'Não encontrei nos documentos selecionados: '
MISSING_PARTS_SEPARATOR = '; '
UNLINKED_CLAIMS_NOTICE = (
    'Parte da resposta foi omitida porque não foi possível vinculá-la às fontes.'
)
# The claims and each fixed text are separate paragraphs.
PARAGRAPH_SEPARATOR = '\n\n'
SENTENCE_END = '.'

READY_STATUS = 'ready'
# One retry on provider calls (PRD §6.2).
PROVIDER_MAX_RETRIES = 1
# Matches `<trecho` and `</trecho` in any case, so chunk text cannot open or close
# a context block (prompt injection defence, PRD §6.3).
TRECHO_TAG_PATTERN = re.compile(r'</?trecho', re.IGNORECASE)
# Citation-like markers the model may write in its texts, such as `[3]`, `[1, 2]`
# or `[1-3]`. They are removed: only the code writes markers (RF-12).
MODEL_MARKER_PATTERN = re.compile(r'\[\s*\d+(?:\s*[,;\-–]\s*\d+)*\s*\]')
WHITESPACE_PATTERN = re.compile(r'\s+')
SPACE_BEFORE_PUNCTUATION_PATTERN = re.compile(r'\s+([.,;:!?…])')
# Final punctuation kept after a claim's markers: `texto.` -> `texto [1].`
TRAILING_PUNCTUATION_PATTERN = re.compile(r'[.!?…]+$')
# Dropped from the end of a claim or missing part before the code adds its own.
TRAILING_SEPARATORS = ' ,;:.'

_PROMPT = ChatPromptTemplate.from_messages(
    [('system', ANSWER_PROMPT_V2), ('human', QUESTION_PROMPT_V1)]
)


# Structured output schema from PRD §6.2 step 6. Internal only: it never crosses
# the HTTP contract. No docstrings or field descriptions: they would be sent to
# the model on top of the prompt. `has_evidence` comes last so the model writes
# the claims and missing parts before deciding it.
class Claim(BaseModel):
    text: str
    cited: list[int]


class AnswerOutput(BaseModel):
    claims: list[Claim]
    missing: list[str]
    has_evidence: bool


class AssembledAnswer(BaseModel):
    """Answer written by the code from the valid claims, plus counts for the log."""

    answer: str
    cited: list[int]
    valid_claims: int
    dropped_claims: int
    missing_parts: int


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


def _clean_model_text(text: str) -> str:
    """Remove `<trecho` tags and `[n]` markers written by the model and normalise
    spaces, so only the code decides which markers the answer shows."""
    text = MODEL_MARKER_PATTERN.sub('', _clean_chunk_text(text))
    text = WHITESPACE_PATTERN.sub(' ', text)
    return SPACE_BEFORE_PUNCTUATION_PATTERN.sub(r'\1', text).strip()


def _claim_sentence(text: str, cited: list[int]) -> str:
    """`texto.` with [1, 3] -> `texto [1][3].` (markers before the final period)."""
    match = TRAILING_PUNCTUATION_PATTERN.search(text)
    end = match.group() if match else SENTENCE_END
    body = (text[: match.start()] if match else text).rstrip(TRAILING_SEPARATORS)
    markers = ''.join(f'[{index}]' for index in cited)
    return f'{body} {markers}{end}'


def _missing_part(text: str) -> str:
    """A missing part as a phrase that follows `MISSING_PARTS_PREFIX`. The case is
    kept as the model wrote it, so proper nouns and acronyms are not changed."""
    return _clean_model_text(text).rstrip(TRAILING_SEPARATORS)


def _assemble_answer(
    output: AnswerOutput | None, chunk_count: int
) -> AssembledAnswer | None:
    """Steps 7-8: write the answer from the claims, or None for the fixed answer.

    A claim is kept only when it has text, cites at least one chunk and every cited
    index exists (1..n). Otherwise it is dropped as unverified. Each kept claim gets
    its own markers; the answer never shows a marker the code did not write.
    """
    if output is None or not output.has_evidence:
        return None
    sentences: list[str] = []
    cited: set[int] = set()
    dropped = 0
    for claim in output.claims:
        text = _clean_model_text(claim.text)
        if not text:
            continue
        indices = sorted(set(claim.cited))
        if not indices or any(index < 1 or index > chunk_count for index in indices):
            dropped += 1
            continue
        sentences.append(_claim_sentence(text, indices))
        cited.update(indices)
    if not sentences:
        return None

    missing = [part for part in map(_missing_part, output.missing) if part]
    paragraphs = [' '.join(sentences)]
    if missing:
        paragraphs.append(
            MISSING_PARTS_PREFIX + MISSING_PARTS_SEPARATOR.join(missing) + SENTENCE_END
        )
    if dropped:
        paragraphs.append(UNLINKED_CLAIMS_NOTICE)
    return AssembledAnswer(
        answer=PARAGRAPH_SEPARATOR.join(paragraphs),
        cited=sorted(cited),
        valid_claims=len(sentences),
        dropped_claims=dropped,
        missing_parts=len(missing),
    )


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
    assembled: AssembledAnswer | None,
) -> None:
    """Log only IDs, counts, flags and duration (never question or answer)."""
    logger.info(
        'query_done document_ids=%s chunk_count=%d llm_called=%s '
        'model_has_evidence=%s has_evidence=%s cited_count=%d valid_claims=%d '
        'dropped_claims=%d missing_parts=%d duration_ms=%d',
        ','.join(document_ids),
        chunk_count,
        chunk_count > 0,
        output.has_evidence if output is not None else None,
        assembled is not None,
        len(assembled.cited) if assembled else 0,
        assembled.valid_claims if assembled else 0,
        assembled.dropped_claims if assembled else 0,
        assembled.missing_parts if assembled else 0,
        (time.monotonic() - started) * 1000,
    )


def answer_question(request: ChatRequest) -> ChatResponse:
    """Answer one independent question using only the selected documents.

    Applies the two-layer evidence rule (PRD §6.2); when it fails, returns the
    fixed RF-14 answer with `has_evidence=False` and no sources. A partial answer
    keeps the supported claims and names the parts that were not found.

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
        _log_query(started, document_ids, 0, None, None)
        return _no_evidence()

    output = _ask_model(request.question, _build_context(chunks))
    assembled = _assemble_answer(output, len(chunks))
    _log_query(started, document_ids, len(chunks), output, assembled)
    if assembled is None:
        # Layer 2: the model reported no evidence or no claim has valid citations.
        return _no_evidence()

    return ChatResponse(
        answer=assembled.answer,
        has_evidence=True,
        sources=[_source(index, chunks[index - 1]) for index in assembled.cited],
    )
