import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.api import routes_documents
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.services import document_service

API_PREFIX = '/api/v1'


def _configure_logging() -> None:
    """Emit the app's own INFO logs; uvicorn only configures its own loggers."""
    app_logger = logging.getLogger('app')
    if app_logger.handlers:  # avoid duplicates on reload
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    )
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


_configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db.init()
    document_service.fail_interrupted_documents()
    document_service.check_embedding_model()
    yield


app = FastAPI(title='Assistente RAG para documentos', lifespan=lifespan)

register_error_handlers(app)

# Added last so it is the outermost middleware and also covers error responses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=['GET', 'POST', 'DELETE'],
    allow_headers=['Content-Type'],
)

app.include_router(routes_documents.router, prefix=API_PREFIX)


@app.get(f'{API_PREFIX}/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}
