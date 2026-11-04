"""Question answering over the selected documents (PRD §6.2, §13)."""

import html
import logging
import re
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document as LCDocument
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app import db
from app.core.config import MIN_QUESTION_CHARS, settings
from app.core.errors import AppError, ErrorCode
from app.schemas.chat import (
    ChatHistoryMessage,
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    Source,
)
from app.services.document_service import get_vector_store, provider_error_code
from app.services.prompts import (
    ANSWER_NO_SOURCES_PROMPT_V1,
    ANSWER_NO_SOURCES_PROMPT_V2,
    ANSWER_PROMPT_V2,
    ANSWER_PROMPT_V3,
    QUERY_REWRITE_PROMPT_V1,
    QUESTION_PROMPT_V1,
)

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
# The query rewrite has a cheap fallback (the original question), so it is
# never retried (PRD §13.4).
REWRITE_MAX_RETRIES = 0
# Matches `<trecho` and `</trecho` in any case, so chunk text cannot open or close
# a context block (prompt injection defence, PRD §6.3).
TRECHO_TAG_PATTERN = re.compile(r'</?trecho', re.IGNORECASE)
# With history (PRD §13.6), `<historico`/`</historico` are neutralised as well,
# so neither the history nor a chunk can open or close the history block.
HISTORY_PATH_TAG_PATTERN = re.compile(r'</?(?:trecho|historico)', re.IGNORECASE)
# Citation-like markers the model may write in its texts, such as `[3]`, `[1, 2]`
# or `[1-3]`. They are removed: only the code writes markers (RF-12).
MODEL_MARKER_PATTERN = re.compile(r'\[\s*\d+(?:\s*[,;\-–]\s*\d+)*\s*\]')
WHITESPACE_PATTERN = re.compile(r'\s+')
SPACE_BEFORE_PUNCTUATION_PATTERN = re.compile(r'\s+([.,;:!?…])')
# A `[n]` marker of a previous answer plus the spaces or tabs before it, so
# `texto [1].` becomes `texto.` (newlines of markdown answers are kept).
HISTORY_MARKER_PATTERN = re.compile(r'[ \t]*' + MODEL_MARKER_PATTERN.pattern)
# How each history message is labelled inside the `<historico>` block.
HISTORY_ROLE_LABELS = {'user': 'Usuário', 'assistant': 'Assistente'}
HISTORY_MESSAGE_SEPARATOR = '\n\n'
# Final punctuation kept after a claim's markers: `texto.` -> `texto [1].`
TRAILING_PUNCTUATION_PATTERN = re.compile(r'[.!?…]+$')
# Dropped from the end of a claim or missing part before the code adds its own.
TRAILING_SEPARATORS = ' ,;:.'

_PROMPT = ChatPromptTemplate.from_messages(
    [('system', ANSWER_PROMPT_V2), ('human', QUESTION_PROMPT_V1)]
)

# Streaming path: prose answer, no structured output (PRD §12.7).
_STREAM_PROMPT = ChatPromptTemplate.from_messages(
    [('system', ANSWER_NO_SOURCES_PROMPT_V1), ('human', QUESTION_PROMPT_V1)]
)

# History-aware versions (PRD §13.7 step 4), used only when the request carries
# history; the human message is still the ORIGINAL question (§13.8, decision 5).
_PROMPT_WITH_HISTORY = ChatPromptTemplate.from_messages(
    [('system', ANSWER_PROMPT_V3), ('human', QUESTION_PROMPT_V1)]
)
_STREAM_PROMPT_WITH_HISTORY = ChatPromptTemplate.from_messages(
    [('system', ANSWER_NO_SOURCES_PROMPT_V2), ('human', QUESTION_PROMPT_V1)]
)

# Query rewrite (PRD §13.7 step 2): plain text output, used only for retrieval.
_REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [('system', QUERY_REWRITE_PROMPT_V1), ('human', QUESTION_PROMPT_V1)]
)

# SSE event payloads yielded by `stream_answer` (PRD §12.6); the route
# renders them as `data: {json}` lines.
StreamEvent = dict[str, object]


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
    # Prompt chunk indices (1..n) of the cited chunks, ordered by the public
    # number they received: `cited[k - 1]` is the chunk shown as `[k]`.
    cited: list[int]
    valid_claims: int
    dropped_claims: int
    missing_parts: int


@dataclass(frozen=True)
class _QueryPlan:
    """What the history changes in one query (PRD §13.7); no LangChain types.

    `history_text` is empty when there is no usable history, and then every
    prompt is exactly the one used without history (V2/V1).
    """

    retrieval_question: str
    history_text: str = ''
    history_turns: int = 0
    rewritten: bool = False
    rewrite_ms: int | None = None


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


ScoredChunk = tuple[LCDocument, float]


def _search(
    store: Any, question: str, k: int, where: dict[str, Any]
) -> list[ScoredChunk]:
    """One filtered search, keeping only chunks at or above the threshold."""
    try:
        results = store.similarity_search_with_relevance_scores(
            question, k=k, filter=where
        )
    except Exception as exc:
        if provider_error_code(exc) is None:
            raise
        raise _provider_failure(exc, 'retrieval') from exc
    return [
        (doc, score) for doc, score in results if score >= settings.relevance_threshold
    ]


def _chunk_key(chunk: LCDocument) -> tuple[str, object]:
    """Identity of a chunk across searches (its vector ID is
    `{document_id}:{chunk_index}`); falls back to the text without an index."""
    metadata = chunk.metadata
    index = metadata.get('chunk_index')
    return (
        str(metadata.get('document_id', '')),
        index if index is not None else chunk.page_content,
    )


def _merge_with_quota(
    global_results: list[ScoredChunk],
    per_document: list[list[ScoredChunk]],
    limit: int,
) -> list[ScoredChunk]:
    """Task 7.29: reserve each document's best chunks, then fill by global rank.

    `per_document` holds, for each selected document, its own top chunks above
    the threshold (best first). Reserved chunks are taken rank by rank across
    documents (every document's 1st chunk, then every 2nd...), each rank by
    score, so when the reservations alone exceed `limit` the cut keeps one
    chunk per document for as many documents as fit. The free slots are filled
    from the global ranking without duplicates, and the result is sorted by
    score, most relevant first. Never more than `limit` chunks.
    """
    selected: dict[tuple[str, object], ScoredChunk] = {}
    depth = max((len(results) for results in per_document), default=0)
    for rank in range(depth):
        tier = [results[rank] for results in per_document if rank < len(results)]
        for doc, score in sorted(tier, key=lambda item: item[1], reverse=True):
            if len(selected) >= limit:
                break
            selected.setdefault(_chunk_key(doc), (doc, score))
    for doc, score in global_results:
        if len(selected) >= limit:
            break
        selected.setdefault(_chunk_key(doc), (doc, score))
    return sorted(selected.values(), key=lambda item: item[1], reverse=True)


def _retrieve(question: str, document_ids: list[str]) -> list[LCDocument]:
    """Steps 2-3: top `RETRIEVAL_K` chunks of the selected documents, filtered by
    `RELEVANCE_THRESHOLD`, most relevant first.

    With two or more documents and `MIN_CHUNKS_PER_DOCUMENT > 0`, each document
    also gets its own filtered search, so a small document whose chunks pass
    the same threshold is not crowded out by a large one (task 7.29). With a
    single document only the global search runs, as before.
    """
    store = get_vector_store()
    global_search = (settings.retrieval_k, {'document_id': {'$in': document_ids}})
    quota = min(settings.min_chunks_per_document, settings.retrieval_k)
    if len(document_ids) < 2 or quota == 0:
        return [doc for doc, _ in _search(store, question, *global_search)]
    searches = [global_search] + [
        (quota, {'document_id': document_id}) for document_id in document_ids
    ]
    # Each search embeds the question again, so they run concurrently: the
    # latency stays close to one search instead of growing with the number of
    # documents. Read-only queries; results come back in submission order.
    with ThreadPoolExecutor(max_workers=len(searches)) as executor:
        results = list(
            executor.map(lambda search: _search(store, question, *search), searches)
        )
    merged = _merge_with_quota(results[0], results[1:], settings.retrieval_k)
    return [doc for doc, _ in merged]


def _clean_chunk_text(text: str, pattern: re.Pattern[str] = TRECHO_TAG_PATTERN) -> str:
    """Remove `<trecho`/`</trecho` (or every tag `pattern` matches) until none is
    left: a removal may form a new tag."""
    while pattern.search(text):
        text = pattern.sub('', text)
    return text


def _clean_history_text(text: str) -> str:
    """Neutralise one history message before it goes into a prompt (PRD §13.6).

    Removes `<historico`/`</historico` and `<trecho`/`</trecho` tags and the
    `[n]` markers of previous answers, so the model cannot reuse an old
    numbering, and repeats until nothing changes: removing a marker may form a
    tag (`<tre[1]cho`) and removing a tag may form a marker.
    """
    while True:
        cleaned = HISTORY_MARKER_PATTERN.sub(
            '', _clean_chunk_text(text, HISTORY_PATH_TAG_PATTERN)
        )
        if cleaned == text:
            return text.strip()
        text = cleaned


def _build_history(history: list[ChatHistoryMessage]) -> str:
    """The cleaned history, one labelled message per paragraph, oldest first.

    Messages left empty by the cleaning are skipped; when none is left the
    result is empty and the query runs as if there were no history.
    """
    messages = []
    for message in history:
        content = _clean_history_text(message.content)
        if content:
            messages.append(f'{HISTORY_ROLE_LABELS[message.role]}: {content}')
    return HISTORY_MESSAGE_SEPARATOR.join(messages)


def _history_turns(history: list[ChatHistoryMessage]) -> int:
    """Number of exchanges for the log: messages / 2, rounded up (PRD §13.4).

    Matches the `2 x MAX_HISTORY_TURNS` message limit and is 0 only for an
    empty history.
    """
    return (len(history) + 1) // 2


def _ask_rewrite_model(question: str, history: str) -> str:
    """Call the chat model once (no retry) for the standalone question.

    Exceptions propagate unchanged; `_rewrite_question` turns every failure
    into the fallback to the original question.
    """
    model = ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.openai_api_key,
        temperature=settings.chat_temperature,
        timeout=settings.provider_timeout_s,
        max_retries=REWRITE_MAX_RETRIES,
    )
    message = (_REWRITE_PROMPT | model).invoke(
        {'history': history, 'question': question}
    )
    content = getattr(message, 'content', None)
    return content if isinstance(content, str) else ''


def _rewrite_question(question: str, history: list[ChatHistoryMessage]) -> str:
    """Task 8.3: the question as a standalone one, for retrieval only.

    Returns `question` unchanged, without calling the model, when the history
    is empty (after cleaning) or `QUERY_REWRITE_ENABLED=false`. A failure, a
    timeout or an invalid output (empty or outside 3..`MAX_QUESTION_CHARS`
    after `strip`) also returns the original question: the rewrite is an
    improvement, never a reason to fail the query (PRD §13.8, decision 3).
    Logs carry only the `error_code`, never any text.
    """
    history_text = _build_history(history)
    if not history_text or not settings.query_rewrite_enabled:
        return question
    try:
        output = _ask_rewrite_model(question, history_text)
    except Exception as exc:
        code = provider_error_code(exc) or ErrorCode.PROVIDER_ERROR
        logger.warning(
            'query_rewrite_failed reason=provider error_code=%s exc_type=%s',
            code.value,
            type(exc).__name__,
        )
        return question
    rewritten = output.strip() if isinstance(output, str) else ''
    if not MIN_QUESTION_CHARS <= len(rewritten) <= settings.max_question_chars:
        logger.warning(
            'query_rewrite_failed reason=invalid_output error_code=%s output_chars=%d',
            ErrorCode.PROVIDER_ERROR.value,
            len(rewritten),
        )
        return question
    return rewritten


def _plan_query(request: ChatRequest) -> _QueryPlan:
    """Steps before retrieval (PRD §13.7): history cleaning and rewrite.

    `rewritten` is true when the question used in retrieval differs from the
    original one (a successful rewrite that returned the question unchanged
    counts as not rewritten); `rewrite_ms` is set whenever the rewrite was
    attempted, including a fallback.
    """
    history_text = _build_history(request.history)
    turns = _history_turns(request.history)
    if not history_text or not settings.query_rewrite_enabled:
        return _QueryPlan(request.question, history_text, turns)
    started = time.monotonic()
    question = _rewrite_question(request.question, request.history)
    return _QueryPlan(
        retrieval_question=question,
        history_text=history_text,
        history_turns=turns,
        rewritten=question != request.question,
        rewrite_ms=int((time.monotonic() - started) * 1000),
    )


def _page(metadata: dict[str, Any]) -> int | None:
    """1-based page from chunk metadata, or None when absent or invalid."""
    page = metadata.get('page')
    if isinstance(page, int) and not isinstance(page, bool) and page >= 1:
        return page
    return None


def _build_context(chunks: list[LCDocument], with_history: bool = False) -> str:
    """Step 5: number chunks 1..n in the PRD §6.3 `<trecho>` format.

    With history, `<historico` tags are removed from the chunks too, so a PDF
    cannot close the history block; without it the context is unchanged.
    """
    pattern = HISTORY_PATH_TAG_PATTERN if with_history else TRECHO_TAG_PATTERN
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        filename = html.escape(str(chunk.metadata.get('filename', '')), quote=True)
        page = _page(chunk.metadata)
        blocks.append(
            f'<trecho id="{index}" arquivo="{filename}" '
            f'pagina="{page if page is not None else ""}">\n'
            f'{_clean_chunk_text(chunk.page_content, pattern).strip()}\n'
            '</trecho>'
        )
    return '\n\n'.join(blocks)


def _ask_model(question: str, context: str, history: str = '') -> AnswerOutput | None:
    """Step 6: call the chat model with structured output.

    With `history`, `ANSWER_PROMPT_V3` is used; without it, `ANSWER_PROMPT_V2`
    with exactly the same input as before the history existed.
    """
    model = ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.openai_api_key,
        temperature=settings.chat_temperature,
        timeout=settings.provider_timeout_s,
        max_retries=PROVIDER_MAX_RETRIES,
    )
    prompt = _PROMPT_WITH_HISTORY if history else _PROMPT
    values = {'context': context, 'question': question}
    if history:
        values['history'] = history
    chain = prompt | model.with_structured_output(AnswerOutput, method='json_schema')
    try:
        result = chain.invoke(values)
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


class _MarkerStreamFilter:
    """Remove `[n]` markers the model may still write in the streaming path.

    A short buffer retains the suffix of the pending text that a later chunk
    could still turn into a marker (`[`, `[3`, `[3,` ... even with the index
    split across chunks) and the whitespace a removal would clean up, so the
    concatenation of every `feed()` result with `flush()` equals the filter
    applied to the whole text at once. Double spaces and spaces before
    punctuation are cleaned only around removals — never elsewhere — so
    newlines and markdown lists survive. A bracket that no text can turn into
    a marker (e.g. `[anexo]`) is literal content and is kept, and so is an
    incomplete bracket that the stream ends with.
    """

    # A pending suffix that more text could still complete into a marker.
    # Over-accepting is safe: whatever a later chunk (or the `flush`)
    # disproves is released as literal text.
    _MARKER_PREFIX_PATTERN = re.compile(
        r'\[\s*\d*(?:\s*[,;\-–]\s*\d*)*\s*(?:[,;\-–]\s*)?'
    )

    def __init__(self) -> None:
        self._buffer = ''

    def feed(self, text: str) -> str:
        """Filter one model chunk; the result may lag one chunk behind it."""
        return self._process(text, final=False)

    def flush(self) -> str:
        """Release everything still buffered at the end of the stream."""
        return self._process('', final=True)

    def _process(self, text: str, final: bool) -> str:
        pending = self._buffer + text
        out: list[str] = []
        pos = 0
        while pos < len(pending):
            bracket = pending.find('[', pos)
            if bracket == -1:
                rest = pending[pos:]
                keep = len(rest) if final else self._retained_start(rest)
                if keep:
                    out.append(rest[:keep])
                self._buffer = rest[keep:]
                break
            match = MODEL_MARKER_PATTERN.match(pending, bracket)
            if match is not None:
                left_start = self._whitespace_run_start(pending, pos, bracket)
                right_end = self._whitespace_run_end(pending, match.end())
                if not final and right_end == len(pending):
                    # The whitespace after the marker is still open: the next
                    # chunk decides how this removal is cleaned up.
                    self._defer(out, pending, pos, left_start)
                    break
                if left_start > pos:
                    out.append(pending[pos:left_start])
                next_char = pending[right_end] if right_end < len(pending) else ''
                join = self._removal_join(
                    pending[left_start:bracket],
                    pending[match.end() : right_end],
                    next_char,
                    out,
                )
                if join:
                    out.append(join)
                pos = right_end
                continue
            if not final and self._MARKER_PREFIX_PATTERN.fullmatch(pending, bracket):
                # An incomplete marker: hold it — and the whitespace a
                # removal would consume — until a later chunk resolves it.
                left_start = self._whitespace_run_start(pending, pos, bracket)
                self._defer(out, pending, pos, left_start)
                break
            # A bracket that no text can turn into a marker: literal content.
            out.append(pending[pos : bracket + 1])
            pos = bracket + 1
        else:
            self._buffer = ''
        return ''.join(out)

    def _defer(self, out: list[str], pending: str, pos: int, left_start: int) -> None:
        """Hold `pending[left_start:]` for the next chunk (or the flush).

        Empty pieces are never appended to `out`, so `out[-1] == ' '` always
        means "a space left by the previous removal" for the check below.
        """
        if left_start > pos:
            out.append(pending[pos:left_start])
        self._buffer = pending[left_start:]
        if out and out[-1] == ' ':
            # That space came from the removal just before this point; the
            # next chunk may collapse or drop it, so keep it uncommitted.
            self._buffer = ' ' + self._buffer
            out.pop()

    def _removal_join(
        self, left_ws: str, right_ws: str, next_char: str, out: list[str]
    ) -> str:
        """What replaces a removed marker and its surrounding whitespace.

        Newlines are preserved (paragraphs and lists are content); spaces and
        tabs around the removal collapse to one space, or to none when the
        next character is punctuation or the previous removal already left
        one. The cleanup is local to the removal: it never touches the rest
        of the text.
        """
        combined = left_ws + right_ws
        if not combined:
            join = ''
        elif '\n' in combined:
            join = ''.join(char for char in combined if char == '\n')
        else:
            join = ' '
        if '\n' in join:
            return join
        punct_next = bool(next_char) and bool(
            SPACE_BEFORE_PUNCTUATION_PATTERN.match(' ' + next_char)
        )
        if punct_next:
            # `texto [3], resto` -> `texto, resto`
            join = ''
        if join == '' and punct_next and out and out[-1] == ' ':
            # A space left by the previous removal now dangles right before
            # the punctuation: `a [1] [3], b` -> `a, b`.
            out.pop()
        elif join == ' ' and out and out[-1] == ' ':
            # Adjacent removals: `a [1] [3] b` -> `a b`, not `a  b`.
            join = ''
        return join

    @staticmethod
    def _retained_start(rest: str) -> int:
        """Index of the trailing whitespace run of `rest` (0 when it is all
        whitespace): a marker in a later chunk may consume it."""
        matches = list(WHITESPACE_PATTERN.finditer(rest))
        if matches and matches[-1].end() == len(rest):
            return matches[-1].start()
        return len(rest)

    @staticmethod
    def _whitespace_run_start(pending: str, pos: int, bracket: int) -> int:
        """Start of the whitespace run before `bracket`, never crossing `pos`
        (whitespace already consumed by an earlier removal stays consumed)."""
        start = bracket
        while start > pos and pending[start - 1].isspace():
            start -= 1
        return start

    @staticmethod
    def _whitespace_run_end(pending: str, end: int) -> int:
        """End of the whitespace run that starts at `end`."""
        match = WHITESPACE_PATTERN.match(pending, end)
        return match.end() if match is not None else end


def _sentence_body(text: str) -> tuple[str, str]:
    """Split a claim into (body without trailing separators, final punctuation)."""
    match = TRAILING_PUNCTUATION_PATTERN.search(text)
    end = match.group() if match else SENTENCE_END
    body = (text[: match.start()] if match else text).rstrip(TRAILING_SEPARATORS)
    return body, end


def _claim_sentence(text: str, cited: list[int]) -> str:
    """`texto.` with [1, 3] -> `texto [1][3].` (markers before the final period)."""
    body, end = _sentence_body(text)
    markers = ''.join(f'[{index}]' for index in cited)
    return f'{body} {markers}{end}'


def _plain_sentence(text: str) -> str:
    """`texto.` stays `texto.` — the sentence and punctuation handling of
    `_claim_sentence` without the `[n]` markers (PRD §12.6, `show_sources=false`)."""
    body, end = _sentence_body(text)
    return f'{body}{end}'


def _missing_part(text: str) -> str:
    """A missing part as a phrase that follows `MISSING_PARTS_PREFIX`. The case is
    kept as the model wrote it, so proper nouns and acronyms are not changed."""
    return _clean_model_text(text).rstrip(TRAILING_SEPARATORS)


def _assemble_answer(
    output: AnswerOutput | None,
    chunk_count: int,
    show_sources: bool = True,
) -> AssembledAnswer | None:
    """Steps 7-8: write the answer from the claims, or None for the fixed answer.

    A claim is kept only when it has text, cites at least one chunk and every cited
    index exists (1..n). Otherwise it is dropped as unverified. Each kept claim gets
    its own markers; the answer never shows a marker the code did not write. The
    markers are renumbered 1..m in order of first appearance in the answer (a
    chunk cited twice keeps one number), so they never expose the chunk's
    position in the prompt. With `show_sources=False` the same claims become
    plain sentences (no `[n]` markers) and the caller answers with no sources
    (PRD §12.6).
    """
    if output is None or not output.has_evidence:
        return None
    sentences: list[str] = []
    # Prompt chunk index -> public marker number, in order of first appearance.
    numbering: dict[int, int] = {}
    dropped = 0
    for claim in output.claims:
        text = _clean_model_text(claim.text)
        if not text:
            continue
        indices = sorted(set(claim.cited))
        if not indices or any(index < 1 or index > chunk_count for index in indices):
            dropped += 1
            continue
        for index in indices:
            numbering.setdefault(index, len(numbering) + 1)
        if show_sources:
            numbers = sorted(numbering[index] for index in indices)
            sentences.append(_claim_sentence(text, numbers))
        else:
            sentences.append(_plain_sentence(text))
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
        cited=list(numbering),
        valid_claims=len(sentences),
        dropped_claims=dropped,
        missing_parts=len(missing),
    )


def _source(index: int, chunk: LCDocument) -> Source:
    """Step 8: public source shown as marker `[index]`, with a truncated excerpt."""
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
    *,
    show_sources: bool = True,
    stream: bool = False,
    first_token_ms: int | None = None,
    has_evidence: bool | None = None,
    plan: _QueryPlan | None = None,
) -> None:
    """Log only IDs, counts, flags and duration (never question, history,
    rewritten question or answer)."""
    if has_evidence is None:
        has_evidence = assembled is not None
    message = (
        'query_done document_ids=%s chunk_count=%d llm_called=%s '
        'model_has_evidence=%s has_evidence=%s cited_count=%d valid_claims=%d '
        'dropped_claims=%d missing_parts=%d '
        'show_sources=%s stream=%s '
        'history_turns=%d rewritten=%s rewrite_ms=%s'
    )
    args: tuple[object, ...] = (
        ','.join(document_ids),
        chunk_count,
        chunk_count > 0,
        output.has_evidence if output is not None else None,
        has_evidence,
        len(assembled.cited) if assembled else 0,
        assembled.valid_claims if assembled else 0,
        assembled.dropped_claims if assembled else 0,
        assembled.missing_parts if assembled else 0,
        show_sources,
        stream,
        plan.history_turns if plan else 0,
        plan.rewritten if plan else False,
        plan.rewrite_ms if plan else None,
    )
    if first_token_ms is not None:
        # Only the streaming path measures the time to the first delta.
        message += ' first_token_ms=%d'
        args += (first_token_ms,)
    message += ' duration_ms=%d'
    args += ((time.monotonic() - started) * 1000,)
    logger.info(message, *args)


def answer_question(request: ChatRequest) -> ChatResponse:
    """Answer one independent question using only the selected documents.

    With history, the question is first rewritten for retrieval and the
    history goes to the answer prompt as data (PRD §13.7); layer 1 is decided
    on the chunks retrieved for the rewritten question.

    Applies the two-layer evidence rule (PRD §6.2); when it fails, returns the
    fixed RF-14 answer with `has_evidence=False` and no sources. A partial answer
    keeps the supported claims and names the parts that were not found. With
    `show_sources=False` the same pipeline runs (both layers intact), but the
    answer is assembled without `[n]` markers and `sources` is empty
    (PRD §12.6).

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

    plan = _plan_query(request)
    chunks = _retrieve(plan.retrieval_question, document_ids)
    if not chunks:
        # Layer 1: nothing relevant enough, so the model is not called.
        _log_query(
            started,
            document_ids,
            0,
            None,
            None,
            show_sources=request.show_sources,
            plan=plan,
        )
        return _no_evidence()

    # The ORIGINAL question is answered (PRD §13.8, decision 5); the history
    # argument is passed only when there is one, so a query without history
    # calls the model exactly as before.
    context = _build_context(chunks, with_history=bool(plan.history_text))
    if plan.history_text:
        output = _ask_model(request.question, context, plan.history_text)
    else:
        output = _ask_model(request.question, context)
    assembled = _assemble_answer(output, len(chunks), request.show_sources)
    _log_query(
        started,
        document_ids,
        len(chunks),
        output,
        assembled,
        show_sources=request.show_sources,
        plan=plan,
    )
    if assembled is None:
        # Layer 2: the model reported no evidence or no claim has valid citations.
        return _no_evidence()

    if not request.show_sources:
        return ChatResponse(answer=assembled.answer, has_evidence=True, sources=[])

    return ChatResponse(
        answer=assembled.answer,
        has_evidence=True,
        sources=[
            _source(number, chunks[index - 1])
            for number, index in enumerate(assembled.cited, start=1)
        ],
    )


def _stream_model(question: str, context: str, history: str = '') -> Iterator[str]:
    """Stream the no-sources answer as text pieces (PRD §12.7).

    With `history`, `ANSWER_NO_SOURCES_PROMPT_V2` is used; without it,
    `ANSWER_NO_SOURCES_PROMPT_V1` with exactly the same input as before.

    Provider failures are mapped to `AppError` from inside the returned
    generator; closing it (for example when the client disconnects) closes the
    model stream too, so the provider iteration really stops.
    """
    model = ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.openai_api_key,
        temperature=settings.chat_temperature,
        timeout=settings.provider_timeout_s,
        max_retries=PROVIDER_MAX_RETRIES,
    )
    prompt = _STREAM_PROMPT_WITH_HISTORY if history else _STREAM_PROMPT
    values = {'context': context, 'question': question}
    if history:
        values['history'] = history
    stream = (prompt | model).stream(values)
    try:
        for event in stream:
            if isinstance(event.content, str) and event.content:
                yield event.content
    except Exception as exc:
        raise _provider_failure(exc, 'generation') from exc
    finally:
        stream.close()


def _no_evidence_events(
    document_ids: list[str], started: float, plan: _QueryPlan
) -> Iterator[StreamEvent]:
    """Layer 1 in the streaming path: the fixed answer, model never called."""
    first_token_ms = int((time.monotonic() - started) * 1000)
    yield {'type': 'delta', 'text': NO_EVIDENCE_ANSWER}
    _log_query(
        started,
        document_ids,
        0,
        None,
        None,
        show_sources=False,
        stream=True,
        first_token_ms=first_token_ms,
        plan=plan,
    )
    yield {'type': 'done', 'has_evidence': False}


def _generation_events(
    question: str,
    context: str,
    document_ids: list[str],
    chunk_count: int,
    started: float,
    plan: _QueryPlan,
) -> Iterator[StreamEvent]:
    """Stream the answer deltas (filtered) and exactly one final `done` event.

    Layer 2 does not apply here: the prose answer carries no citations to
    validate (PRD §12.7); grounding comes from layer 1 plus the prompt rules.
    """
    marker_filter = _MarkerStreamFilter()
    first_token_ms: int | None = None
    if plan.history_text:
        model_stream = _stream_model(question, context, plan.history_text)
    else:
        model_stream = _stream_model(question, context)
    try:
        for piece in model_stream:
            text = marker_filter.feed(piece)
            if not text:
                continue
            if first_token_ms is None:
                first_token_ms = int((time.monotonic() - started) * 1000)
            yield {'type': 'delta', 'text': text}
        tail = marker_filter.flush()
        if tail:
            if first_token_ms is None:
                first_token_ms = int((time.monotonic() - started) * 1000)
            yield {'type': 'delta', 'text': tail}
    except GeneratorExit:
        # The client disconnected: stop the model iteration, keep the log to
        # IDs, counts and durations.
        logger.info(
            'query_cancelled document_ids=%s chunk_count=%d first_token_ms=%s '
            'duration_ms=%d',
            ','.join(document_ids),
            chunk_count,
            first_token_ms,
            (time.monotonic() - started) * 1000,
        )
        raise
    finally:
        # `_stream_model` returns a generator: closing it stops the provider
        # iteration instead of only the client's read.
        close = getattr(model_stream, 'close', None)
        if close is not None:
            close()
    _log_query(
        started,
        document_ids,
        chunk_count,
        None,
        None,
        show_sources=False,
        stream=True,
        first_token_ms=first_token_ms,
        has_evidence=True,
        plan=plan,
    )
    yield {'type': 'done', 'has_evidence': True}


def stream_answer(request: ChatStreamRequest) -> Iterator[StreamEvent]:
    """Stream a no-sources answer for one question (PRD §12.6, §12.7).

    A regular function, not a generator: validation, the query rewrite (with
    history, PRD §13.7) and retrieval run eagerly,
    so `document_not_ready` (409) and retrieval failures/timeouts (502/504)
    are raised BEFORE the stream starts. Only then is the event generator
    returned. Layer 1 still decides in code: without a relevant chunk the
    fixed RF-14 answer is streamed as a single delta and the model is never
    called. The generator yields the SSE event payloads as dicts; the route
    renders them as `data: {json}` lines.

    Raises the same `AppError`s as `answer_question` for the pre-stream steps;
    provider failures during the generation are raised from the generator.
    """
    started = time.monotonic()
    document_ids = list(dict.fromkeys(str(item) for item in request.document_ids))
    _ensure_ready(document_ids)
    _ensure_provider_configured()

    # The rewrite (with history) runs here too, before the stream opens.
    plan = _plan_query(request)
    chunks = _retrieve(plan.retrieval_question, document_ids)
    if not chunks:
        return _no_evidence_events(document_ids, started, plan)
    return _generation_events(
        request.question,
        _build_context(chunks, with_history=bool(plan.history_text)),
        document_ids,
        len(chunks),
        started,
        plan,
    )
