from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import register_error_handlers

API_PREFIX = '/api/v1'

app = FastAPI(title='Assistente RAG para documentos')

register_error_handlers(app)

# Added last so it is the outermost middleware and also covers error responses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=['GET', 'POST', 'DELETE'],
    allow_headers=['Content-Type'],
)


@app.get(f'{API_PREFIX}/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}
