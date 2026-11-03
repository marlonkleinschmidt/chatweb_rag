"""Upload validation (RF-02, PRD §5.3): rejections, acceptance, duplicates."""

import uuid

from app import db
from app.core.config import settings
from app.services import document_service

BYTES_PER_MB = 1024 * 1024


def test_upload_valid_pdf_is_accepted(upload, make_pdf):
    response = upload(make_pdf())

    assert response.status_code == 202
    body = response.json()
    assert body['filename'] == 'doc.pdf'
    assert body['status'] == 'received'
    assert body['warning'] is None
    assert body['error_code'] is None
    assert body['page_count'] is None
    # storage_path and sha256 never cross the HTTP contract (PRD §5.1)
    assert 'storage_path' not in body
    assert 'sha256' not in body
    # the file is stored under its UUID and the row exists in `received`
    document_id = body['id']
    uuid.UUID(document_id)
    assert (settings.documents_dir / f'{document_id}.pdf').exists()
    assert db.get(document_id)['status'] == 'received'


def test_upload_empty_file_returns_file_empty(upload, assert_error):
    response = upload(b'')

    assert_error(response, 422, 'file_empty', 'O arquivo está vazio.')


def test_upload_without_file_field_returns_invalid_request(client, assert_error):
    response = client.post('/api/v1/documents')

    assert_error(response, 422, 'invalid_request', 'Os dados enviados são inválidos.')


def test_upload_non_pdf_extension_returns_file_not_pdf(upload, make_pdf, assert_error):
    response = upload(make_pdf(), filename='documento.txt')

    assert_error(response, 422, 'file_not_pdf', 'Envie um arquivo PDF válido.')


def test_upload_without_pdf_signature_returns_file_not_pdf(upload, assert_error):
    response = upload(b'this file has no PDF magic number at all')

    assert_error(response, 422, 'file_not_pdf', 'Envie um arquivo PDF válido.')


def test_upload_too_large_file_returns_file_too_large(
    upload, make_pdf, monkeypatch, assert_error
):
    monkeypatch.setattr(settings, 'max_upload_mb', 1)
    content = make_pdf() + b'0' * BYTES_PER_MB

    response = upload(content)

    assert_error(response, 413, 'file_too_large', 'O arquivo excede o limite de 1 MB.')


def test_upload_encrypted_pdf_returns_pdf_encrypted(
    upload, make_encrypted_pdf, assert_error
):
    response = upload(make_encrypted_pdf())

    assert_error(
        response,
        422,
        'pdf_encrypted',
        'PDFs protegidos por senha não são suportados.',
    )


def test_upload_too_many_pages_returns_pdf_too_many_pages(
    upload, make_pdf, monkeypatch, assert_error
):
    monkeypatch.setattr(settings, 'max_pdf_pages', 1)

    response = upload(make_pdf(2))

    assert_error(
        response,
        422,
        'pdf_too_many_pages',
        'O PDF excede o limite de 1 páginas.',
    )


def test_upload_duplicate_content_returns_warning(upload, make_pdf):
    content = make_pdf()
    first = upload(content)
    second = upload(content, filename='copy.pdf')

    assert first.status_code == 202
    assert first.json()['warning'] is None
    assert second.status_code == 202
    body = second.json()
    # duplicates are accepted as distinct documents, with the RF-01 warning
    assert body['warning'] == 'Este arquivo já foi enviado.'
    assert body['id'] != first.json()['id']
    assert db.get(body['id']) is not None


def test_upload_schedules_background_indexing(client, monkeypatch, upload, make_pdf):
    scheduled = []
    monkeypatch.setattr(document_service, 'index_document', scheduled.append)

    response = upload(make_pdf())

    assert response.status_code == 202
    assert scheduled == [response.json()['id']]
