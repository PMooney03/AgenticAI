"""In-process metrics for live traffic.

Prometheus-style counters and rolling latency windows, without a sidecar. The snapshot
is what ``GET /metrics`` returns. Nothing stored here is user content: counts, timings,
token totals, tool names, and quality *scores* only.

In production this store would be replaced by Prometheus histograms / OpenTelemetry;
the signals would be the same.
"""

from __future__ import annotations

import re
import threading
from collections import Counter, deque
from dataclasses import dataclass

_HEX_ID = re.compile(r"^[0-9a-fA-F-]{16,}$")


def normalise_route(path: str) -> str:
    """Collapse request/document ids so cardinality stays bounded."""
    parts = [part for part in path.split("/") if part]
    templated = ["{id}" if _HEX_ID.match(part) else part for part in parts]
    return "/" + "/".join(templated) if templated else "/"


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((p / 100) * (len(ordered) - 1))))
    return float(ordered[index])


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


@dataclass(frozen=True, slots=True)
class ChatObservation:
    mode: str
    llm_ms: int
    retrieval_ms: int
    retrieved_chunks: int
    cited_sources: int
    prompt_tokens: int | None
    completion_tokens: int | None
    tools: list[str]
    paused: bool
    refused: bool
    citation_rate: float | None
    groundedness: float | None


class MetricsStore:
    def __init__(self, window: int = 200) -> None:
        self._lock = threading.Lock()
        self._http_requests = 0
        self._http_errors = 0
        self._routes: Counter[str] = Counter()
        self._chats = 0
        self._chats_completed = 0
        self._chats_paused = 0
        self._chats_rag = 0
        self._chats_refused = 0
        self._tool_calls = 0
        self._tools: Counter[str] = Counter()
        self._approvals_approved = 0
        self._approvals_rejected = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._llm_ms: deque[int] = deque(maxlen=window)
        self._retrieval_ms: deque[int] = deque(maxlen=window)
        self._citation_rates: deque[float] = deque(maxlen=window)
        self._groundedness: deque[float] = deque(maxlen=window)

    def observe_http(self, *, method: str, path: str, status_code: int) -> None:
        route = f"{method} {normalise_route(path)}"
        with self._lock:
            self._http_requests += 1
            self._routes[route] += 1
            if status_code >= 400:
                self._http_errors += 1

    def observe_chat(self, observation: ChatObservation, *, new: bool = True) -> None:
        with self._lock:
            if new:
                self._chats += 1
            if observation.paused:
                self._chats_paused += 1
                return
            self._chats_completed += 1
            if observation.mode == "rag":
                self._chats_rag += 1
            if observation.refused:
                self._chats_refused += 1
            self._llm_ms.append(observation.llm_ms)
            if observation.retrieval_ms:
                self._retrieval_ms.append(observation.retrieval_ms)
            if observation.prompt_tokens:
                self._prompt_tokens += observation.prompt_tokens
            if observation.completion_tokens:
                self._completion_tokens += observation.completion_tokens
            for name in observation.tools:
                self._tools[name] += 1
                self._tool_calls += 1
            if observation.citation_rate is not None:
                self._citation_rates.append(observation.citation_rate)
            if observation.groundedness is not None:
                self._groundedness.append(observation.groundedness)

    def observe_approval(self, *, approved: bool) -> None:
        with self._lock:
            if approved:
                self._approvals_approved += 1
            else:
                self._approvals_rejected += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            llm = list(self._llm_ms)
            retrieval = list(self._retrieval_ms)
            citations = list(self._citation_rates)
            grounded = list(self._groundedness)
            return {
                "chats": self._chats,
                "chats_completed": self._chats_completed,
                "chats_paused": self._chats_paused,
                "chats_rag": self._chats_rag,
                "chats_refused": self._chats_refused,
                "http_requests": self._http_requests,
                "http_errors": self._http_errors,
                "tool_calls": self._tool_calls,
                "approvals_approved": self._approvals_approved,
                "approvals_rejected": self._approvals_rejected,
                "prompt_tokens": self._prompt_tokens,
                "completion_tokens": self._completion_tokens,
                "llm": _latency_dict(llm),
                "retrieval": _latency_dict(retrieval),
                "citation_rate_avg": _avg(citations),
                "groundedness_avg": _avg(grounded),
                "tools": dict(self._tools),
                "routes": dict(self._routes),
            }


def _latency_dict(values: list[int]) -> dict[str, float | int | None]:
    floats = [float(value) for value in values]
    return {
        "count": len(values),
        "avg_ms": _avg(floats),
        "p50_ms": _percentile(floats, 50),
        "p95_ms": _percentile(floats, 95),
        "max_ms": float(max(values)) if values else None,
    }
