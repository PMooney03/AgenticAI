"""In-memory high-level traces for recent agent runs.

Stores only what the UI and ``GET /agent/trace/{id}`` should see: node names, step
labels, tool names, chunk counts. No questions, answers, document text or planner JSON.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TraceRecord:
    request_id: str
    nodes_visited: list[str]
    workflow: list[dict[str, Any]]
    retrieved_chunks: int
    tools: list[str]
    prompt_version: str
    model: str


class TraceStore:
    def __init__(self, max_entries: int = 200) -> None:
        self._items: OrderedDict[str, TraceRecord] = OrderedDict()
        self._max = max_entries

    def put(self, record: TraceRecord) -> None:
        if record.request_id in self._items:
            del self._items[record.request_id]
        self._items[record.request_id] = record
        while len(self._items) > self._max:
            self._items.popitem(last=False)

    def get(self, request_id: str) -> TraceRecord | None:
        return self._items.get(request_id)
