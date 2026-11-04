import logging
from collections.abc import Awaitable, Callable
from enum import StrEnum

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.schemas.error import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    """Stable error codes from PRD §5.3 plus generic HTTP-level codes."""

    FILE_EMPTY = 'file_empty'
    FILE_NOT_PDF = 'file_not_pdf'
    FILE_TOO_LARGE = 'file_too_large'
    PDF_ENCRYPTED = 'pdf_encrypted'
    PDF_TOO_MANY_PAGES = 'pdf_too_many_pages'
    PDF_NO_TEXT = 'pdf_no_text'
    PROCESSING_INTERRUPTED = 'processing_interrupted'
    DOCUMENT_NOT_FOUND = 'document_not_found'
    DOCUMENT_PROCESSING = 'document_processing'
    DOCUMENT_NOT_READY = 'document_not_ready'
    QUESTION_INVALID = 'question_invalid'
    PROVIDER_ERROR = 'provider_error'
    PROVIDER_TIMEOUT = 'provider_timeout'
    DELETE_PARTIAL = 'delete_partial'
    INTERNAL_ERROR = 'internal_error'
    # v2.2 (PRD §12.6): explicit sources requested on the streaming endpoint.
    STREAM_SOURCES_UNSUPPORTED = 'stream_sources_unsupported'
    # Generic codes (not in PRD §5.3) for framework-level errors.
    INVALID_REQUEST = 'invalid_request'
    NOT_FOUND = 'not_found'
    METHOD_NOT_ALLOWED = 'method_not_allowed'


ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.FILE_EMPTY: 'O arquivo está vazio.',
    ErrorCode.FILE_NOT_PDF: 'Envie um arquivo PDF válido.',
    ErrorCode.FILE_TOO_LARGE: 'O arquivo excede o limite de {n} MB.',
    ErrorCode.PDF_ENCRYPTED: 'PDFs protegidos por senha não são suportados.',
    ErrorCode.PDF_TOO_MANY_PAGES: 'O PDF excede o limite de {n} páginas.',
    ErrorCode.PDF_NO_TEXT: (
        'Este PDF não contém texto pesquisável. '
        'PDFs digitalizados ainda não são suportados.'
    ),
    ErrorCode.PROCESSING_INTERRUPTED: (
        'Processamento interrompido. Remova e envie novamente.'
    ),
    ErrorCode.DOCUMENT_NOT_FOUND: 'Documento não encontrado.',
    ErrorCode.DOCUMENT_PROCESSING: (
        'Aguarde o fim do processamento para remover este documento.'
    ),
    ErrorCode.DOCUMENT_NOT_READY: (
        'Um ou mais documentos selecionados não estão prontos.'
    ),
    ErrorCode.QUESTION_INVALID: 'Escreva uma pergunta entre 3 e {n} caracteres.',
    ErrorCode.PROVIDER_ERROR: (
        'O serviço de IA não respondeu corretamente. Tente novamente.'
    ),
    ErrorCode.PROVIDER_TIMEOUT: (
        'O serviço de IA demorou demais para responder. Tente novamente.'
    ),
    ErrorCode.DELETE_PARTIAL: 'Não foi possível concluir a remoção. Tente novamente.',
    ErrorCode.INTERNAL_ERROR: 'Ocorreu um erro inesperado. Tente novamente.',
    ErrorCode.STREAM_SOURCES_UNSUPPORTED: (
        'O endpoint de streaming não exibe fontes; use /chat/query.'
    ),
    ErrorCode.INVALID_REQUEST: 'Os dados enviados são inválidos.',
    ErrorCode.NOT_FOUND: 'Recurso não encontrado.',
    ErrorCode.METHOD_NOT_ALLOWED: 'Método não permitido.',
}

# `pdf_no_text` and `processing_interrupted` are only stored on failed documents,
# never returned as HTTP responses.
ERROR_STATUS: dict[ErrorCode, int] = {
    ErrorCode.FILE_EMPTY: 422,
    ErrorCode.FILE_NOT_PDF: 422,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.PDF_ENCRYPTED: 422,
    ErrorCode.PDF_TOO_MANY_PAGES: 422,
    ErrorCode.DOCUMENT_NOT_FOUND: 404,
    ErrorCode.DOCUMENT_PROCESSING: 409,
    ErrorCode.DOCUMENT_NOT_READY: 409,
    ErrorCode.QUESTION_INVALID: 422,
    ErrorCode.PROVIDER_ERROR: 502,
    ErrorCode.PROVIDER_TIMEOUT: 504,
    ErrorCode.DELETE_PARTIAL: 500,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.STREAM_SOURCES_UNSUPPORTED: 422,
    ErrorCode.INVALID_REQUEST: 422,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
}


def error_message(code: ErrorCode, **params: object) -> str:
    """Return the pt-BR message for `code`, filling placeholders such as `{n}`."""
    return ERROR_MESSAGES[code].format(**params)


class AppError(Exception):
    """Domain error with a stable code, HTTP status and safe pt-BR message."""

    def __init__(self, code: ErrorCode, **params: object) -> None:
        self.code = code
        self.status_code = ERROR_STATUS[code]
        self.message = error_message(code, **params)
        super().__init__(code.value)


def error_response(
    code: ErrorCode,
    message: str,
    status_code: int,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code.value, message=message))
    return JSONResponse(
        status_code=status_code, content=body.model_dump(), headers=headers
    )


async def _app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.code, exc.message, exc.status_code)


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    if any('question' in error.get('loc', ()) for error in exc.errors()):
        code = ErrorCode.QUESTION_INVALID
        message = error_message(code, n=settings.max_question_chars)
    else:
        code = ErrorCode.INVALID_REQUEST
        message = error_message(code)
    return error_response(code, message, ERROR_STATUS[code])


async def _http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    if exc.status_code == 404:
        code = ErrorCode.NOT_FOUND
    elif exc.status_code == 405:
        code = ErrorCode.METHOD_NOT_ALLOWED
    elif exc.status_code >= 500:
        code = ErrorCode.INTERNAL_ERROR
    else:
        code = ErrorCode.INVALID_REQUEST
    return error_response(
        code, error_message(code), exc.status_code, headers=exc.headers
    )


async def _unhandled_error_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # Runs inside CORSMiddleware, so the 500 envelope still carries CORS headers.
    try:
        return await call_next(request)
    except Exception as exc:
        logger.error(
            'unhandled_error error_code=%s exc_type=%s method=%s path=%s',
            ErrorCode.INTERNAL_ERROR.value,
            type(exc).__name__,
            request.method,
            request.url.path,
        )
        code = ErrorCode.INTERNAL_ERROR
        return error_response(code, error_message(code), ERROR_STATUS[code])


def register_error_handlers(app: FastAPI) -> None:
    """Install handlers that render every error in the PRD §5.3 envelope.

    Must be called before adding CORSMiddleware so CORS stays the outermost layer.
    """
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.middleware('http')(_unhandled_error_middleware)
