"""SQLite catalog of documents (PRD §8.2), with hand-written SQL."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,
    filename      TEXT NOT NULL,
    storage_path  TEXT NOT NULL,
    sha256        TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('received', 'processing', 'ready', 'failed')),
    error_code    TEXT,
    error_message TEXT,
    page_count    INTEGER,
    chunk_count   INTEGER,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at DESC);
"""  # noqa: E501

# Allowed previous states for each target state (PRD §5.2).
ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    'processing': ('received',),
    'ready': ('processing',),
    'failed': ('received', 'processing'),
}


def utc_now() -> str:
    """Current time as ISO 8601 UTC with a trailing `Z`."""
    return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:  # commits on success, rolls back on error
            yield conn
    finally:
        conn.close()


def init() -> None:
    """Create the data directories, the table and the index if missing."""
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    settings.documents_dir.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(SCHEMA)


def create(
    document_id: str,
    filename: str,
    storage_path: str,
    sha256: str,
    size_bytes: int,
) -> dict[str, Any]:
    """Insert a new document in `received` state and return the row."""
    now = utc_now()
    with _connect() as conn:
        conn.execute(
            'INSERT INTO documents (id, filename, storage_path, sha256, size_bytes, '
            "status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'received', ?, ?)",
            (document_id, filename, storage_path, sha256, size_bytes, now, now),
        )
        row = conn.execute(
            'SELECT * FROM documents WHERE id = ?', (document_id,)
        ).fetchone()
    return dict(row)


def get(document_id: str) -> dict[str, Any] | None:
    """Return the row for `document_id`, or `None` if it does not exist."""
    with _connect() as conn:
        row = conn.execute(
            'SELECT * FROM documents WHERE id = ?', (document_id,)
        ).fetchone()
    return dict(row) if row is not None else None


def sha256_exists(sha256: str) -> bool:
    """Return `True` if any stored document has this SHA-256 (RF-01 duplicates)."""
    with _connect() as conn:
        row = conn.execute(
            'SELECT 1 FROM documents WHERE sha256 = ? LIMIT 1', (sha256,)
        ).fetchone()
    return row is not None


def list() -> list[dict[str, Any]]:  # name required by PRD §10
    """Return all rows, most recent first (rowid breaks same-second ties)."""
    with _connect() as conn:
        rows = conn.execute(
            'SELECT * FROM documents ORDER BY created_at DESC, rowid DESC'
        ).fetchall()
    return [dict(row) for row in rows]


def update_status(
    document_id: str,
    status: str,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
    page_count: int | None = None,
    chunk_count: int | None = None,
) -> bool:
    """Move a document to `status` if the transition is allowed (PRD §5.2).

    `error_code`/`error_message` are overwritten (cleared when `None`);
    `page_count`/`chunk_count` are kept when `None`.
    Returns `False` when the document does not exist or the transition is invalid.
    """
    previous = ALLOWED_TRANSITIONS.get(status)
    if previous is None:
        raise ValueError(f'Invalid target status: {status}')
    placeholders = ', '.join('?' for _ in previous)
    with _connect() as conn:
        cursor = conn.execute(
            'UPDATE documents SET status = ?, error_code = ?, error_message = ?, '
            'page_count = COALESCE(?, page_count), '
            'chunk_count = COALESCE(?, chunk_count), updated_at = ? '
            f'WHERE id = ? AND status IN ({placeholders})',
            (
                status,
                error_code,
                error_message,
                page_count,
                chunk_count,
                utc_now(),
                document_id,
                *previous,
            ),
        )
    return cursor.rowcount == 1


def fail_unfinished(error_code: str, error_message: str) -> list[str]:
    """Mark every `received`/`processing` row as `failed` (startup, PRD §5.2).

    Returns the IDs of the rows that changed.
    """
    with _connect() as conn:
        rows = conn.execute(
            "UPDATE documents SET status = 'failed', error_code = ?, "
            'error_message = ?, updated_at = ? '
            "WHERE status IN ('received', 'processing') RETURNING id",
            (error_code, error_message, utc_now()),
        ).fetchall()
    return [row['id'] for row in rows]


def delete(document_id: str) -> bool:
    """Delete the row; idempotent. Returns `True` if a row was removed."""
    with _connect() as conn:
        cursor = conn.execute('DELETE FROM documents WHERE id = ?', (document_id,))
    return cursor.rowcount == 1
