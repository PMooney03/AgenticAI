"""Split pages into overlapping chunks that carry their metadata.

Why chunk at all: embedding models have a context limit and a single vector for a whole
document blurs its topics together. Chunks of a few hundred tokens give precise hits.

Why overlap: a fact that straddles a boundary would otherwise be cut in two; overlap means
at least one chunk contains it whole.

Why LlamaIndex here: ``SentenceSplitter`` respects sentence and paragraph boundaries while
honouring a token budget, which is noticeably better than fixed character windows and not
worth re-implementing. We call ``split_text`` and keep our own ``Chunk`` type so the rest
of the pipeline (and Qdrant payloads) stay framework-independent.
"""

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache

from llama_index.core.node_parser import SentenceSplitter

from app.ingestion.loaders import LoadedPage

# Stable namespace so chunk IDs are reproducible for the same document/page/index.
_CHUNK_NAMESPACE = uuid.UUID("5d1f8b2e-2c4a-4f3e-9a6b-7e0c1d2f3a4b")
_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])|\n{2,}")


def approximate_tokenizer(text: str) -> list[str]:
    """Cheap, offline token approximation (words and punctuation).

    Avoids a network download of a tiktoken vocabulary on first use and is accurate enough
    for budgeting chunk sizes.
    """
    return _TOKEN.findall(text)


def split_sentences(text: str) -> list[str]:
    """Regex sentence splitter used instead of LlamaIndex's default NLTK tokenizer.

    Keeps ingestion free of NLTK data files at runtime (which also sidesteps NLTK 3.10's
    refusal to open hard-linked files inside ``uv``-managed virtualenvs).

    Each returned piece keeps its trailing whitespace so ``"".join(pieces) == text``, which
    is the contract LlamaIndex's splitter relies on when it re-merges sentences.
    """
    pieces: list[str] = []
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        pieces.append(text[start : match.end()])
        start = match.end()
    pieces.append(text[start:])
    return [p for p in pieces if p.strip()]


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    document_id: str
    document_name: str
    chunk_index: int
    text: str
    page: int | None = None
    metadata: dict[str, str | int | None] = field(default_factory=dict)


@lru_cache(maxsize=8)
def _splitter(chunk_size: int, chunk_overlap: int) -> SentenceSplitter:
    return SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        tokenizer=approximate_tokenizer,
        chunking_tokenizer_fn=split_sentences,
        include_metadata=False,
        include_prev_next_rel=False,
    )


def chunk_pages(
    pages: Sequence[LoadedPage],
    *,
    document_id: str,
    document_name: str,
    chunk_size: int,
    chunk_overlap: int,
    extra_metadata: dict[str, str | int | None] | None = None,
) -> list[Chunk]:
    """Chunk every page, numbering chunks sequentially across the document."""
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    splitter = _splitter(chunk_size, chunk_overlap)
    chunks: list[Chunk] = []
    for page in pages:
        for text in splitter.split_text(page.text):
            text = text.strip()
            if not text:
                continue
            index = len(chunks)
            chunks.append(
                Chunk(
                    chunk_id=str(uuid.uuid5(_CHUNK_NAMESPACE, f"{document_id}:{index}")),
                    document_id=document_id,
                    document_name=document_name,
                    chunk_index=index,
                    text=text,
                    page=page.page,
                    metadata=dict(extra_metadata or {}),
                )
            )
    return chunks
