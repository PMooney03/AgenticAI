"""Loaders (metadata extraction), chunking, and the SQLite registry."""

from pathlib import Path

import pytest

from app.ingestion import (
    DocumentRegistry,
    LoadedPage,
    UnsupportedFileError,
    chunk_pages,
    load_pages,
)
from app.ingestion.chunking import approximate_tokenizer, split_sentences
from tests.helpers import make_pdf

# --- loaders -------------------------------------------------------------------------------


def test_load_pdf_yields_one_page_per_pdf_page_with_numbers(tmp_path: Path) -> None:
    path = tmp_path / "two.pdf"
    path.write_bytes(make_pdf(["Alpha is the first page.", "Beta is the second page."]))

    pages = load_pages(path)

    assert [p.page for p in pages] == [1, 2]
    assert "Alpha" in pages[0].text
    assert "Beta" in pages[1].text


def test_load_pdf_drops_blank_pages(tmp_path: Path) -> None:
    path = tmp_path / "gap.pdf"
    path.write_bytes(make_pdf(["Content here.", "", "More content."]))
    pages = load_pages(path)
    assert [p.page for p in pages] == [1, 3]  # page numbers preserved, blank page skipped


def test_load_text_and_markdown_have_no_page_numbers(tmp_path: Path) -> None:
    txt = tmp_path / "notes.txt"
    txt.write_text("plain notes", encoding="utf-8")
    md = tmp_path / "readme.md"
    md.write_text("# Title\n\nBody", encoding="utf-8")

    assert load_pages(txt) == [LoadedPage(text="plain notes", page=None)]
    assert load_pages(md) == [LoadedPage(text="# Title\n\nBody", page=None)]


def test_load_unknown_extension_raises(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("a,b", encoding="utf-8")
    with pytest.raises(UnsupportedFileError):
        load_pages(path)


# --- chunking ------------------------------------------------------------------------------


def _sentences(n: int, prefix: str = "Sentence") -> str:
    return " ".join(f"{prefix} number {i} talks about topic {i}." for i in range(n))


def test_sentence_splitter_preserves_text_and_splits_on_boundaries() -> None:
    text = "First one. Second one!  Third (yes) one? Fourth with 3.5 decimals.\n\nNew para."
    pieces = split_sentences(text)
    assert "".join(pieces) == text
    assert [p.strip() for p in pieces] == [
        "First one.",
        "Second one!",
        "Third (yes) one?",
        "Fourth with 3.5 decimals.",
        "New para.",
    ]


def test_chunks_respect_size_budget_and_overlap() -> None:
    pages = [LoadedPage(text=_sentences(40), page=1)]
    chunks = chunk_pages(
        pages, document_id="d1", document_name="a.pdf", chunk_size=60, chunk_overlap=15
    )

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(approximate_tokenizer(chunk.text)) <= 60

    # Overlap: the last sentence of one chunk reappears at the start of the next.
    last_sentence = chunks[0].text.rsplit(". ", 1)[-1].rstrip(".")
    assert chunks[1].text.startswith(last_sentence)


def test_chunks_carry_metadata_and_sequential_indices() -> None:
    pages = [
        LoadedPage(text=_sentences(12, "P1"), page=1),
        LoadedPage(text=_sentences(12, "P2"), page=2),
    ]
    chunks = chunk_pages(
        pages,
        document_id="doc-1",
        document_name="report.pdf",
        chunk_size=50,
        chunk_overlap=5,
        extra_metadata={"content_type": "application/pdf"},
    )

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert {c.document_id for c in chunks} == {"doc-1"}
    assert {c.document_name for c in chunks} == {"report.pdf"}
    assert {c.page for c in chunks} == {1, 2}
    assert all(c.metadata == {"content_type": "application/pdf"} for c in chunks)
    # Page-1 chunks come before page-2 chunks.
    pages_in_order = [c.page for c in chunks]
    assert pages_in_order == sorted(pages_in_order)


def test_chunk_ids_are_unique_uuids_and_deterministic() -> None:
    pages = [LoadedPage(text=_sentences(30), page=None)]
    kwargs = dict(document_id="same", document_name="n.txt", chunk_size=40, chunk_overlap=5)
    a = chunk_pages(pages, **kwargs)
    b = chunk_pages(pages, **kwargs)
    ids = [c.chunk_id for c in a]
    assert len(set(ids)) == len(ids)
    assert ids == [c.chunk_id for c in b]
    assert all(len(i) == 36 for i in ids)


def test_chunking_rejects_overlap_not_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        chunk_pages([], document_id="d", document_name="n", chunk_size=10, chunk_overlap=10)


def test_short_text_is_a_single_chunk() -> None:
    chunks = chunk_pages(
        [LoadedPage(text="Tiny.", page=None)],
        document_id="d",
        document_name="n.txt",
        chunk_size=100,
        chunk_overlap=10,
    )
    assert len(chunks) == 1
    assert chunks[0].text == "Tiny."


# --- registry ------------------------------------------------------------------------------


def test_registry_lifecycle(tmp_path: Path) -> None:
    registry = DocumentRegistry(tmp_path / "r.db")
    rec = registry.create(
        document_id="abc", name="a.pdf", content_type="application/pdf", size_bytes=10
    )
    assert rec.status == "processing"
    assert registry.count_ready() == 0

    registry.mark_ready("abc", chunk_count=5, page_count=2)
    ready = registry.get("abc")
    assert ready is not None
    assert (ready.status, ready.chunk_count, ready.page_count) == ("ready", 5, 2)
    assert registry.count_ready() == 1
    assert [d.id for d in registry.list()] == ["abc"]

    assert registry.delete("abc") is True
    assert registry.delete("abc") is False
    assert registry.get("abc") is None


def test_registry_marks_failed_with_truncated_error(tmp_path: Path) -> None:
    registry = DocumentRegistry(tmp_path / "r.db")
    registry.create(document_id="x", name="x.txt", content_type="text/plain", size_bytes=1)
    registry.mark_failed("x", error="boom " * 200)
    rec = registry.get("x")
    assert rec is not None
    assert rec.status == "failed"
    assert rec.error is not None and len(rec.error) <= 500
