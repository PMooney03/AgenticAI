"""Build the grounded context block and the source list that accompanies an answer.

Each retrieved chunk becomes a numbered excerpt. The number is the only thing the model
needs to cite; the API maps it back to filename, page and score for the UI.
"""

from dataclasses import dataclass

from app.retrieval.base import RetrievedChunk

_SNIPPET_CHARS = 240
_EMPTY_CONTEXT = "(No relevant excerpts were found in the uploaded documents.)"


@dataclass(frozen=True, slots=True)
class Source:
    label: int  # 1-based, matches "[Source N]" in the answer
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None
    score: float
    snippet: str


def _location(chunk: RetrievedChunk) -> str:
    return f"{chunk.document_name}, page {chunk.page}" if chunk.page else chunk.document_name


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _SNIPPET_CHARS else text[: _SNIPPET_CHARS - 3] + "..."


def build_context(chunks: list[RetrievedChunk]) -> tuple[str, list[Source]]:
    """Return the context text for the prompt and the parallel list of sources."""
    if not chunks:
        return _EMPTY_CONTEXT, []

    blocks: list[str] = []
    sources: list[Source] = []
    for label, chunk in enumerate(chunks, start=1):
        # Neutralise delimiter look-alikes inside document text so an excerpt cannot
        # pretend to close itself and start injecting "instructions" outside the block.
        body = chunk.text.replace("<<<", "< < <").replace(">>>", "> > >").strip()
        blocks.append(f"[Source {label}] {_location(chunk)}\n<<<\n{body}\n>>>")
        sources.append(
            Source(
                label=label,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                page=chunk.page,
                score=round(chunk.score, 4),
                snippet=_snippet(chunk.text),
            )
        )
    return "\n\n".join(blocks), sources
