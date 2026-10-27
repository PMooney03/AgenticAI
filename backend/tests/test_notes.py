from pathlib import Path

import pytest

from app.notes.store import MAX_NOTE_CHARS, NoteError, NoteStore


def test_append_writes_jsonl(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "notes.jsonl")
    note = store.append(text="Buy milk", title="todo")
    raw = (tmp_path / "notes.jsonl").read_text(encoding="utf-8")
    assert note.id in raw
    assert "Buy milk" in raw
    assert "todo" in raw


def test_append_rejects_empty_and_huge(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "notes.jsonl")
    with pytest.raises(NoteError, match="empty"):
        store.append(text="  ")
    with pytest.raises(NoteError, match="longer"):
        store.append(text="x" * (MAX_NOTE_CHARS + 1))
    assert not (tmp_path / "notes.jsonl").exists()
