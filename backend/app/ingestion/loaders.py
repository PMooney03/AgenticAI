"""Turn an uploaded file into a list of text pages with metadata.

Where LlamaIndex is used, and why:
- PDF: ``llama_index.readers.file.PDFReader`` (built on ``pypdf``) returns one
  ``Document`` per page with a ``page_label``. Page-level granularity is what lets us cite
  "report.pdf, page 7" in answers, so this reader earns its place.
- TXT / Markdown: a reader adds nothing over ``Path.read_text`` - there are no pages and no
  structure we need to preserve beyond the text itself - so we read them directly rather
  than routing through a framework for appearances.
"""

from dataclasses import dataclass
from pathlib import Path

from llama_index.readers.file import PDFReader


class UnsupportedFileError(ValueError):
    """The file extension has no loader."""


@dataclass(frozen=True, slots=True)
class LoadedPage:
    text: str
    page: int | None  # 1-based page number for PDFs; None when the format has no pages


def _load_pdf(path: Path) -> list[LoadedPage]:
    documents = PDFReader(return_full_document=False).load_data(path)
    pages: list[LoadedPage] = []
    for index, document in enumerate(documents, start=1):
        label = document.metadata.get("page_label")
        try:
            page = int(label) if label is not None else index
        except (TypeError, ValueError):
            page = index
        text = document.text.strip()
        if text:
            pages.append(LoadedPage(text=text, page=page))
    return pages


def _load_text(path: Path) -> list[LoadedPage]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    return [LoadedPage(text=text, page=None)] if text else []


_LOADERS = {
    ".pdf": _load_pdf,
    ".txt": _load_text,
    ".md": _load_text,
}


def load_pages(path: Path) -> list[LoadedPage]:
    """Load a file into pages. Empty pages (e.g. scanned images without OCR) are dropped."""
    loader = _LOADERS.get(path.suffix.lower())
    if loader is None:
        raise UnsupportedFileError(f"No loader for '{path.suffix}' files.")
    return loader(path)
