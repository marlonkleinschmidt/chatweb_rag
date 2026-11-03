from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse
from app.services import rag_service

router = APIRouter(prefix='/chat', tags=['chat'])


@router.post('/query', response_model=ChatResponse)
def query(request: ChatRequest) -> ChatResponse:
    # Sync endpoint: the RAG call blocks on OpenAI, so FastAPI runs it in a
    # threadpool. Domain errors (409/502/504) are AppError, rendered globally.
    return rag_service.answer_question(request)
