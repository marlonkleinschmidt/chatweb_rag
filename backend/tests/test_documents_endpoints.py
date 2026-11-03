"""Document endpoints (PRD §5.1): listing, detail, deletion."""

import uuid

from app import db
from app.core.config import settings
from app.services import document_service

API_DOCUMENTS = '/api/v1/documents'


def test_get_document_with_non_uuid_id_returns_404(client, assert_error):
    response = client.get(f'{API_DOCUMENTS}/not-a-uuid')

    assert_error(response, 404, 'document_not_found', 'Documento não encontrado.')


def test_get_document_with_unknown_uuid_returns_404(client, assert_error):
    unknown_id = str(uuid.uuid4())

    response = client.get(f'{API_DOCUMENTS}/{unknown_id}')

    assert_error(response, 404, 'document_not_found', 'Documento não encontrado.')


def test_get_document_returns_the_catalog_fields(client, make_ready_document):
    document_id = make_ready_document('manual.pdf', page_count=10, chunk_count=39)

    response = client.get(f'{API_DOCUMENTS}/{document_id}')

    assert response.status_code == 200
    body = response.json()
    assert body['id'] == document_id
    assert body['filename'] == 'manual.pdf'
    assert body['status'] == 'ready'
    assert body['page_count'] == 10
    assert body['chunk_count'] == 39
    assert body['error_code'] is None
    # storage_path and sha256 never cross the HTTP contract (PRD §5.1)
    assert 'storage_path' not in body
    assert 'sha256' not in body


def test_delete_received_document_returns_409(client, insert_document, assert_error):
    document_id = insert_document()

    response = client.delete(f'{API_DOCUMENTS}/{document_id}')

    assert_error(
        response,
        409,
        'document_processing',
        'Aguarde o fim do processamento para remover este documento.',
    )


def test_delete_processing_document_returns_409(client, insert_document, assert_error):
    document_id = insert_document()
    assert db.update_status(document_id, 'processing') is True

    response = client.delete(f'{API_DOCUMENTS}/{document_id}')

    assert_error(response, 409, 'document_processing')
    assert db.get(document_id)['status'] == 'processing'


def test_delete_ready_document_removes_vectors_file_and_record(
    client, make_ready_document, add_vectors
):
    document_id = make_ready_document()
    add_vectors(document_id)
    file_path = settings.documents_dir / f'{document_id}.pdf'
    file_path.write_bytes(b'%PDF-placeholder')
    store = document_service.get_vector_store(with_embeddings=False)
    assert store.get(where={'document_id': document_id})['ids']

    response = client.delete(f'{API_DOCUMENTS}/{document_id}')

    assert response.status_code == 204
    assert response.content == b''
    # removal order: vectors -> file -> record, all gone (PRD §8.3)
    assert store.get(where={'document_id': document_id})['ids'] == []
    assert not file_path.exists()
    assert db.get(document_id) is None


def test_delete_twice_returns_404(client, make_ready_document, assert_error):
    document_id = make_ready_document()
    assert client.delete(f'{API_DOCUMENTS}/{document_id}').status_code == 204

    response = client.delete(f'{API_DOCUMENTS}/{document_id}')

    assert_error(response, 404, 'document_not_found', 'Documento não encontrado.')


def test_list_documents_returns_newest_first(client, upload, make_pdf):
    assert upload(make_pdf(), filename='first.pdf').status_code == 202
    assert upload(make_pdf(2), filename='second.pdf').status_code == 202

    response = client.get(API_DOCUMENTS)

    assert response.status_code == 200
    body = response.json()
    assert [item['filename'] for item in body['items']] == [
        'second.pdf',
        'first.pdf',
    ]
    assert body['embedding_model_changed'] is False
    for item in body['items']:
        assert 'storage_path' not in item
        assert 'sha256' not in item


def test_list_documents_flags_embedding_model_change(
    client, make_ready_document, add_vectors
):
    document_id = make_ready_document()
    add_vectors(document_id, embedding_model='old-embedding-model')

    response = client.get(API_DOCUMENTS)

    assert response.status_code == 200
    assert response.json()['embedding_model_changed'] is True
