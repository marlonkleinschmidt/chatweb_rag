"""Document status machine (PRD §5.2): legal transitions and startup orphans."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app import db
from app.core.errors import ErrorCode, error_message
from app.main import app
from app.services import document_service


def _move_to(document_id: str, status: str) -> None:
    """Walk the legal path from `received` to `status`."""
    if status != 'received':
        assert db.update_status(document_id, 'processing') is True
    if status in ('ready', 'failed'):
        assert db.update_status(document_id, status) is True


ALLOWED_TRANSITIONS = [
    ('received', 'processing'),
    ('processing', 'ready'),
    ('received', 'failed'),
    ('processing', 'failed'),
]


@pytest.mark.parametrize(('start', 'target'), ALLOWED_TRANSITIONS)
def test_allowed_transition_updates_status(insert_document, start, target):
    document_id = insert_document()
    _move_to(document_id, start)

    assert db.update_status(document_id, target) is True
    assert db.get(document_id)['status'] == target


FORBIDDEN_TRANSITIONS = [
    ('received', 'ready'),
    ('processing', 'processing'),
    ('ready', 'processing'),
    ('ready', 'ready'),
    ('failed', 'processing'),
    ('failed', 'ready'),
]


@pytest.mark.parametrize(('start', 'target'), FORBIDDEN_TRANSITIONS)
def test_forbidden_transition_is_rejected(insert_document, start, target):
    document_id = insert_document()
    _move_to(document_id, start)

    assert db.update_status(document_id, target) is False
    assert db.get(document_id)['status'] == start


def test_update_status_returns_false_for_unknown_document():
    unknown_id = str(uuid.uuid4())

    assert db.update_status(unknown_id, 'processing') is False


@pytest.mark.parametrize('target', ['deleted', 'received'])
def test_update_status_rejects_unknown_target_status(insert_document, target):
    document_id = insert_document()

    with pytest.raises(ValueError):
        db.update_status(document_id, target)

    assert db.get(document_id)['status'] == 'received'


def test_failed_transition_stores_error_code(insert_document):
    document_id = insert_document()
    message = error_message(ErrorCode.PDF_NO_TEXT)

    updated = db.update_status(
        document_id,
        'failed',
        error_code=ErrorCode.PDF_NO_TEXT.value,
        error_message=message,
    )

    assert updated is True
    row = db.get(document_id)
    assert row['status'] == 'failed'
    assert row['error_code'] == 'pdf_no_text'
    assert row['error_message'] == message


def test_fail_interrupted_documents_marks_orphans(insert_document):
    received_id = insert_document()
    processing_id = insert_document()
    ready_id = insert_document()
    failed_id = insert_document()
    _move_to(processing_id, 'processing')
    _move_to(ready_id, 'ready')
    _move_to(failed_id, 'failed')

    document_service.fail_interrupted_documents()

    interrupted_message = error_message(ErrorCode.PROCESSING_INTERRUPTED)
    for document_id in (received_id, processing_id):
        row = db.get(document_id)
        assert row['status'] == 'failed'
        assert row['error_code'] == 'processing_interrupted'
        assert row['error_message'] == interrupted_message
    assert db.get(ready_id)['status'] == 'ready'
    assert db.get(failed_id)['status'] == 'failed'


def test_startup_marks_orphans_as_failed(insert_document):
    received_id = insert_document()
    processing_id = insert_document()
    _move_to(processing_id, 'processing')

    # entering the TestClient context runs the app startup (main.py lifespan)
    with TestClient(app) as test_client:
        for document_id in (received_id, processing_id):
            row = db.get(document_id)
            assert row['status'] == 'failed'
            assert row['error_code'] == 'processing_interrupted'
        response = test_client.get(f'/api/v1/documents/{received_id}')
        assert response.status_code == 200
        body = response.json()
        assert body['status'] == 'failed'
        assert body['error_code'] == 'processing_interrupted'
