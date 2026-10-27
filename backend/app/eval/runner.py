"""Run the golden set against the real graph with fakes.

Offline eval must not talk to Ollama or the Docker Qdrant. It uses FakeLLMProvider,
FakeEmbeddingProvider and Qdrant's in-process ``:memory:`` store so CI and ``POST /eval/run``
stay deterministic and fast. Live traffic is scored separately by ``MetricsStore``.
"""

from __future__ import annotations

import tempfile
import time
import uuid
from pathlib import Path

from app.agent.graph import Agent, AgentResult
from app.embeddings import FakeEmbeddingProvider
from app.eval.cases import GOLDEN_CASES, GoldenCase
from app.ingestion.chunking import Chunk
from app.llm import FakeLLMProvider
from app.mcp.client import InProcessMCPClient
from app.mcp.server import build_mcp_server
from app.retrieval import QdrantVectorStore, Retriever
from app.schemas.eval import EvalCaseResult, EvalReport


def _chunks_for(case: GoldenCase) -> list[Chunk]:
    chunks: list[Chunk] = []
    for index, (name, text) in enumerate(case.documents):
        document_id = uuid.uuid5(uuid.NAMESPACE_URL, f"eval:{case.id}:{name}").hex
        chunks.append(
            Chunk(
                chunk_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{index}")),
                document_id=document_id,
                document_name=name,
                chunk_index=index,
                text=text,
                page=1,
            )
        )
    return chunks


async def _build_agent(case: GoldenCase, notes_path: Path) -> Agent:
    embeddings = FakeEmbeddingProvider()
    llm = FakeLLMProvider(replies=list(case.replies), model="eval-fake")
    store = QdrantVectorStore(location=":memory:", collection=f"eval-{case.id}")
    chunks = _chunks_for(case)
    if chunks:
        vectors = await embeddings.embed_documents([chunk.text for chunk in chunks])
        await store.upsert(chunks, vectors)
    retriever = Retriever(embeddings=embeddings, store=store, default_top_k=4)
    tools = InProcessMCPClient(build_mcp_server(notes_path=notes_path))
    return Agent(llm=llm, retriever=retriever, tools=tools, max_steps=3)


def _source_blob(result: AgentResult) -> str:
    parts: list[str] = []
    for source in result.sources:
        parts.append(str(source.get("snippet") or ""))
        parts.append(str(source.get("document_name") or ""))
    return " ".join(parts).lower()


def _score_case(
    case: GoldenCase, result: AgentResult, *, paused: AgentResult | None, notes_path: Path
) -> EvalCaseResult:
    checks: dict[str, bool] = {}
    failures: list[str] = []

    def check(name: str, ok: bool) -> None:
        checks[name] = ok
        if not ok:
            failures.append(name)

    if case.expect_nodes:
        check("nodes", all(node in result.nodes_visited for node in case.expect_nodes))
    if case.expect_tool is not None:
        check("tool", case.expect_tool in result.tool_names)
    if case.expect_tool_output is not None:
        outputs = " ".join(str(item.get("output") or "") for item in result.tool_calls)
        check("tool_output", case.expect_tool_output in outputs)
    if case.expect_retrieval_contains is not None:
        check("retrieval", case.expect_retrieval_contains.lower() in _source_blob(result))
    if case.expect_cited is True:
        check("cited", bool(result.cited_labels))
    elif case.expect_cited is False:
        check("cited", not result.cited_labels)
    if case.expect_refusal is not None:
        check("refusal", result.refused is case.expect_refusal)
    if case.expect_pending:
        check("paused", paused is not None and paused.pending_approval is not None)
        check("resolved", result.pending_approval is None)
    if case.expect_note_contains is not None:
        text = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
        check("note_written", case.expect_note_contains in text)
    if case.expect_groundedness_min is not None:
        score = result.groundedness if result.groundedness is not None else -1.0
        check("groundedness", score >= case.expect_groundedness_min)

    return EvalCaseResult(
        id=case.id,
        passed=not failures,
        checks=checks,
        failures=failures,
        nodes_visited=result.nodes_visited,
        tools=result.tool_names,
        retrieved_chunks=result.retrieved_chunks,
        cited_sources=len(result.cited_labels),
        citation_rate=result.citation_rate,
        groundedness=result.groundedness,
        refused=result.refused,
        pending=result.pending_approval is not None,
        llm_ms=result.llm_ms,
    )


async def _run_case(case: GoldenCase, tmp: Path) -> EvalCaseResult:
    notes_path = tmp / f"{case.id}.jsonl"
    agent = await _build_agent(case, notes_path)
    thread_id = f"eval-{case.id}"
    first = await agent.run(
        question=case.question,
        history=[],
        use_documents=case.use_documents,
        thread_id=thread_id,
    )
    paused = first if first.pending_approval else None
    result = first
    if case.resume is not None:
        result = await agent.resume(thread_id, approved=case.resume)
    return _score_case(case, result, paused=paused, notes_path=notes_path)


async def run_golden_eval() -> EvalReport:
    started = time.perf_counter()
    results: list[EvalCaseResult] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for case in GOLDEN_CASES:
            results.append(await _run_case(case, tmp_path))
    passed = sum(1 for item in results if item.passed)
    return EvalReport(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        duration_ms=int((time.perf_counter() - started) * 1000),
        cases=results,
    )
