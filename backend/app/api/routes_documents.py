from fastapi import APIRouter, BackgroundTasks, UploadFile

from app.schemas.document import (
    Document,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.services import document_service

router = APIRouter(prefix='/documents', tags=['documents'])


@router.post('', status_code=202, response_model=DocumentUploadResponse)
def upload_document(
    file: UploadFile, background_tasks: BackgroundTasks
) -> DocumentUploadResponse:
    # Sync endpoint: FastAPI runs it in a threadpool, so blocking I/O is fine here.
    document = document_service.upload_document(file.filename, file.file)
    # Runs after the 202 is sent; the service lock keeps indexing sequential.
    background_tasks.add_task(document_service.index_document, str(document.id))
    return document


@router.get('', response_model=DocumentListResponse)
def list_documents() -> DocumentListResponse:
    return DocumentListResponse(
        items=document_service.list_documents(),
        embedding_model_changed=document_service.embedding_model_changed(),
    )


# `document_id` is a plain string so an invalid UUID yields 404, not 422.
@router.get('/{document_id}', response_model=Document)
def get_document(document_id: str) -> Document:
    return document_service.get_document(document_id)


@router.delete('/{document_id}', status_code=204)
def delete_document(document_id: str) -> None:
    document_service.delete_document(document_id)
