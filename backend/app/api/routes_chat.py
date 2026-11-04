import json
from collections.abc import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.errors import AppError, ErrorCode
from app.schemas.chat import ChatRequest, ChatResponse, ChatStreamRequest
from app.services import rag_service
from app.services.rag_service import StreamEvent

router = APIRouter(prefix='/chat', tags=['chat'])


@router.post('/query', response_model=ChatResponse)
def query(request: ChatRequest) -> ChatResponse:
    # Sync endpoint: the RAG call blocks on OpenAI, so FastAPI runs it in a
    # threadpool. Domain errors (409/502/504) are AppError, rendered globally.
    return rag_service.answer_question(request)


@router.post('/query/stream')
def query_stream(request: ChatStreamRequest) -> StreamingResponse:
    # Only an explicit `show_sources=true` fails: the field defaults to false
    # on this route, and the endpoint never generates citations (PRD §12.6).
    if request.show_sources:
        raise AppError(ErrorCode.STREAM_SOURCES_UNSUPPORTED)
    # Runs before the response exists, so validation and retrieval errors
    # (409/502/504) are rendered by the global handler as JSON envelopes.
    events = rag_service.stream_answer(request)
    return StreamingResponse(
        _sse_lines(events),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache'},
    )


def _sse_lines(events: Iterator[StreamEvent]) -> Iterator[str]:
    """Render each event payload as one SSE line (PRD §12.6).

    A provider failure during the generation becomes a final `error` event
    with the §5.3 envelope (the 200 status is already committed); when the
    client disconnects, closing this generator closes the service generator
    and with it the model stream.
    """
    try:
        for event in events:
            yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'
    except AppError as exc:
        error = {
            'type': 'error',
            'error': {'code': exc.code.value, 'message': exc.message},
        }
        yield f'data: {json.dumps(error, ensure_ascii=False)}\n\n'
    finally:
        close = getattr(events, 'close', None)
        if close is not None:
            close()
