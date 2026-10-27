"""Cheap, deterministic quality scores for RAG answers.

These are *proxies*, not an LLM-as-judge. Retrieval and generation are scored separately:

- citation_rate: of the chunks we retrieved, how many did the answer actually cite?
- groundedness: of the content words in the answer, what fraction also appear in the
  evidence (retrieved chunk text and/or tool output)?
- refused: did the model use the allowed "documents do not contain enough" path?

The same functions score live chat (online) and the golden set (offline). Scores never
store the answer or the chunks — only numbers — so they are safe to keep in metrics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REFUSAL_PHRASE = "the uploaded documents do not contain enough information"

_CITATION = re.compile(r"\[source\s+\d+\]", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOP = frozenset(
    {
        "a",
        "about",
        "after",
        "also",
        "an",
        "and",
        "answer",
        "are",
        "as",
        "at",
        "be",
        "been",
        "before",
        "being",
        "but",
        "by",
        "can",
        "did",
        "do",
        "document",
        "documents",
        "does",
        "enough",
        "for",
        "from",
        "general",
        "had",
        "has",
        "have",
        "her",
        "his",
        "if",
        "in",
        "information",
        "into",
        "is",
        "it",
        "its",
        "just",
        "knowledge",
        "not",
        "of",
        "on",
        "only",
        "or",
        "our",
        "over",
        "so",
        "source",
        "sources",
        "than",
        "that",
        "the",
        "their",
        "then",
        "this",
        "to",
        "too",
        "uploaded",
        "very",
        "was",
        "we",
        "were",
        "will",
        "with",
        "you",
        "your",
    }
)


@dataclass(frozen=True, slots=True)
class QualityScore:
    refused: bool
    citation_rate: float | None
    groundedness: float | None
    cited_sources: int
    retrieved_chunks: int
    overlap_tokens: int
    answer_tokens: int


def is_refusal(answer: str) -> bool:
    return REFUSAL_PHRASE in answer.lower()


def strip_citations(text: str) -> str:
    return _CITATION.sub(" ", text)


def content_tokens(text: str) -> set[str]:
    """Content words: skip stopwords; keep numbers and tokens longer than two letters."""
    tokens: set[str] = set()
    for raw in _WORD.findall(strip_citations(text).lower()):
        if raw in _STOP:
            continue
        if raw.isdigit() or len(raw) > 2:
            tokens.add(raw)
    return tokens


def citation_rate(cited: int, retrieved: int, *, refused: bool) -> float | None:
    if refused or retrieved <= 0:
        return None
    return round(cited / retrieved, 4)


def groundedness_score(answer: str, evidence: list[str], *, refused: bool) -> float | None:
    if refused:
        return 1.0
    corpus = [text for text in evidence if text.strip()]
    if not corpus:
        return None
    answer_tokens = content_tokens(answer)
    if not answer_tokens:
        return None
    evidence_tokens: set[str] = set()
    for text in corpus:
        evidence_tokens |= content_tokens(text)
    if not evidence_tokens:
        return 0.0
    return round(len(answer_tokens & evidence_tokens) / len(answer_tokens), 4)


def score_quality(
    *,
    answer: str,
    retrieved_chunks: int,
    cited_labels: list[int],
    evidence_texts: list[str],
) -> QualityScore:
    refused = is_refusal(answer)
    cited = len(cited_labels)
    answer_tokens = content_tokens(answer)
    evidence_tokens: set[str] = set()
    for text in evidence_texts:
        evidence_tokens |= content_tokens(text)
    overlap = answer_tokens & evidence_tokens
    return QualityScore(
        refused=refused,
        citation_rate=citation_rate(cited, retrieved_chunks, refused=refused),
        groundedness=groundedness_score(answer, evidence_texts, refused=refused),
        cited_sources=cited,
        retrieved_chunks=retrieved_chunks,
        overlap_tokens=len(overlap),
        answer_tokens=len(answer_tokens),
    )
