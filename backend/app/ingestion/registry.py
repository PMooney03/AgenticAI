"""SQLite-backed registry of uploaded documents.

Qdrant holds chunks; this table holds *documents* (name, size, status, chunk count) so the
UI can list them and the API can report ingestion progress or failure. Plain ``sqlite3``
from the standard library is sufficient: a single small table, low write volume.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

DocumentStatus = Literal["processing", "ready", "failed"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    content_type  TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    status        TEXT NOT NULL,
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    page_count    INTEGER,
    error         TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    id: str
    name: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    chunk_count: int
    page_count: int | None
    error: str | None
    created_at: datetime
    updated_at: datetime


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _row_to_record(row: sqlite3.Row) -> DocumentRecord:
    return DocumentRecord(
        id=row["id"],
        name=row["name"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        status=row["status"],
        chunk_count=row["chunk_count"],
        page_count=row["page_count"],
        error=row["error"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class DocumentRegistry:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def create(
        self, *, document_id: str, name: str, content_type: str, size_bytes: int
    ) -> DocumentRecord:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents (id, name, content_type, size_bytes, status, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, 'processing', ?, ?)",
                (document_id, name, content_type, size_bytes, now, now),
            )
        record = self.get(document_id)
        assert record is not None
        return record

    def mark_ready(self, document_id: str, *, chunk_count: int, page_count: int | None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE documents SET status='ready', chunk_count=?, page_count=?, error=NULL, "
                "updated_at=? WHERE id=?",
                (chunk_count, page_count, _now(), document_id),
            )

    def mark_failed(self, document_id: str, *, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE documents SET status='failed', error=?, updated_at=? WHERE id=?",
                (error[:500], _now(), document_id),
            )

    def get(self, document_id: str) -> DocumentRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        return _row_to_record(row) if row else None

    def list(self) -> list[DocumentRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [_row_to_record(r) for r in rows]

    def delete(self, document_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id=?", (document_id,))
        return cursor.rowcount > 0

    def count_ready(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM documents WHERE status='ready'"
            ).fetchone()
        return int(row["n"])
