"""Golden cases for the offline eval harness.

Each case pins planner JSON and the final answer so the graph, retriever, tools and
quality scorer can be checked without Ollama. The documents are short on purpose: fake
embeddings are a hashed bag-of-words, so lexical overlap is what retrieval uses here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

HANDBOOK = (
    "Full-time employees receive twenty five days of paid annual leave per year. "
    "The office closes at six in the evening."
)

PLAN_RETRIEVE = '{"action": "retrieve", "tool_name": null, "tool_args": {}}'
PLAN_ANSWER = '{"action": "answer", "tool_name": null, "tool_args": {}}'
PLAN_CALC = (
    '{"action": "tool", "tool_name": "calculator", "tool_args": {"expression": "12 * (3 + 4)"}}'
)
PLAN_CLOCK = '{"action": "tool", "tool_name": "clock", "tool_args": {}}'
PLAN_NOTE = (
    '{"action": "tool", "tool_name": "save_note", '
    '"tool_args": {"text": "Buy milk", "title": "todo"}}'
)

REFUSAL = (
    "The uploaded documents do not contain enough information to answer this. "
    "[General knowledge: Mars has no official capital.]"
)


@dataclass(frozen=True, slots=True)
class GoldenCase:
    id: str
    question: str
    use_documents: bool
    replies: list[str]
    documents: list[tuple[str, str]] = field(default_factory=list)
    expect_nodes: tuple[str, ...] = ()
    expect_tool: str | None = None
    expect_tool_output: str | None = None
    expect_retrieval_contains: str | None = None
    expect_cited: bool | None = None
    expect_refusal: bool | None = None
    expect_pending: bool = False
    resume: bool | None = None
    expect_note_contains: str | None = None
    expect_groundedness_min: float | None = None


GOLDEN_CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        id="retrieve_leave",
        question="How many days of annual leave do employees get?",
        use_documents=True,
        documents=[("handbook.md", HANDBOOK)],
        replies=[PLAN_RETRIEVE, "Full-time employees receive twenty five days [Source 1]."],
        expect_nodes=("plan", "retrieve", "evaluate", "generate_answer"),
        expect_retrieval_contains="twenty five days",
        expect_cited=True,
        expect_refusal=False,
        expect_groundedness_min=0.4,
    ),
    GoldenCase(
        id="refuse_unrelated",
        question="What is the capital of Mars Colony?",
        use_documents=True,
        documents=[("handbook.md", HANDBOOK)],
        replies=[PLAN_RETRIEVE, REFUSAL],
        expect_nodes=("plan", "retrieve", "evaluate", "generate_answer"),
        expect_refusal=True,
        expect_cited=False,
    ),
    GoldenCase(
        id="calculator",
        question="what is 12 times (3+4)?",
        use_documents=False,
        replies=[PLAN_CALC, "The result is 84."],
        expect_nodes=("plan", "call_tool", "evaluate", "generate_answer"),
        expect_tool="calculator",
        expect_tool_output="84",
    ),
    GoldenCase(
        id="clock",
        question="what time is it?",
        use_documents=False,
        replies=[PLAN_CLOCK, "The local time is shown above."],
        expect_nodes=("call_tool", "generate_answer"),
        expect_tool="clock",
    ),
    GoldenCase(
        id="direct_hello",
        question="Hello there.",
        use_documents=False,
        replies=[PLAN_ANSWER, "Hello from the second brain."],
        expect_nodes=("plan", "generate_answer"),
        expect_refusal=False,
    ),
    GoldenCase(
        id="save_note_approve",
        question="remember to buy milk",
        use_documents=False,
        replies=[PLAN_NOTE, "Saved to your notebook."],
        expect_pending=True,
        resume=True,
        expect_nodes=("plan", "call_tool", "evaluate", "generate_answer"),
        expect_tool="save_note",
        expect_note_contains="Buy milk",
    ),
)
