"""Local notebook used by the ``save_note`` MCP tool.

One JSON object per line. This is the only write tool in the allowlist; LangGraph
interrupts before the MCP call so a human can refuse the write.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

MAX_NOTE_CHARS = 2_000
MAX_TITLE_CHARS = 80


class NoteError(ValueError):
    """The note is empty, too long, or otherwise not writable."""


@dataclass(frozen=True, slots=True)
class Note:
    id: str
    title: str
    text: str
    created_at: str


class NoteStore:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def append(self, *, text: str, title: str = "") -> Note:
        body = text.strip()
        if not body:
            raise NoteError("Note text is empty.")
        if len(body) > MAX_NOTE_CHARS:
            raise NoteError(f"Note is longer than {MAX_NOTE_CHARS} characters.")
        heading = title.strip()[:MAX_TITLE_CHARS]
        note = Note(
            id=uuid4().hex,
            title=heading,
            text=body,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": note.id,
            "title": note.title,
            "text": note.text,
            "created_at": note.created_at,
        }
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return note
