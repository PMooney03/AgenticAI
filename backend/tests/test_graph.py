from pathlib import Path

from app.agent import Agent
from app.embeddings import FakeEmbeddingProvider
from app.ingestion.chunking import Chunk
from app.llm import FakeLLMProvider
from app.mcp.client import InProcessMCPClient
from app.mcp.server import build_mcp_server
from app.retrieval import QdrantVectorStore, Retriever

PLAN_RETRIEVE = '{"action": "retrieve", "tool_name": null, "tool_args": {}}'
PLAN_TOOL = (
    '{"action": "tool", "tool_name": "calculator", "tool_args": {"expression": "12 * (3 + 4)"}}'
)
PLAN_ANSWER = '{"action": "answer", "tool_name": null, "tool_args": {}}'
PLAN_CLOCK = '{"action": "tool", "tool_name": "clock", "tool_args": {}}'
PLAN_NOTE = (
    '{"action": "tool", "tool_name": "save_note", '
    '"tool_args": {"text": "Buy milk", "title": "todo"}}'
)


async def _agent(
    llm: FakeLLMProvider,
    embeddings: FakeEmbeddingProvider,
    *,
    chunks: list[Chunk] | None = None,
    notes_path: Path | None = None,
) -> Agent:
    store = QdrantVectorStore(location=":memory:", collection="agent")
    if chunks:
        vectors = await embeddings.embed_documents([chunk.text for chunk in chunks])
        await store.upsert(chunks, vectors)
    retriever = Retriever(embeddings=embeddings, store=store, default_top_k=2)
    tools = None
    if notes_path is not None:
        tools = InProcessMCPClient(build_mcp_server(notes_path=notes_path))
    return Agent(llm=llm, retriever=retriever, tools=tools, max_steps=3)


def _chunk() -> Chunk:
    return Chunk(
        chunk_id="11111111-1111-1111-1111-111111111111",
        document_id="doc",
        document_name="handbook.pdf",
        chunk_index=0,
        text="Employees receive twenty five days of annual leave.",
        page=4,
    )


async def test_graph_retrieves_then_answers(fake_embeddings: FakeEmbeddingProvider) -> None:
    llm = FakeLLMProvider(replies=[PLAN_RETRIEVE, "Twenty five days [Source 1]."])
    agent = await _agent(llm, fake_embeddings, chunks=[_chunk()])

    result = await agent.run(question="how many days of leave?", history=[], use_documents=True)

    assert result.mode == "rag"
    assert result.retrieved_chunks >= 1
    assert result.sources[0]["document_name"] == "handbook.pdf"
    assert result.cited_labels == [1]
    assert result.nodes_visited == ["plan", "retrieve", "evaluate", "generate_answer"]
    labels = [step["label"] for step in result.steps]
    assert labels[:2] == ["Analysed request", "Searched documents"]
    assert result.steps[-1]["label"] == "Generated response"
    assert "twenty five days" in llm.calls[1][0].content


async def test_graph_calls_calculator(fake_embeddings: FakeEmbeddingProvider) -> None:
    llm = FakeLLMProvider(replies=[PLAN_TOOL, "The result is 84."])
    agent = await _agent(llm, fake_embeddings)

    result = await agent.run(question="what is 12 times (3+4)?", history=[], use_documents=False)

    assert result.mode == "chat"
    assert result.tool_names == ["calculator"]
    assert result.tool_calls[0]["output"] == "84"
    assert "call_tool" in result.nodes_visited
    assert any("calculator" in step["label"] for step in result.steps)
    assert "84" in llm.calls[1][0].content
    assert result.prompt_version == "agent-answer-v1"


async def test_graph_calls_clock_over_mcp(fake_embeddings: FakeEmbeddingProvider) -> None:
    llm = FakeLLMProvider(replies=[PLAN_CLOCK, "It is currently that time."])
    agent = await _agent(llm, fake_embeddings)

    result = await agent.run(question="what time is it?", history=[], use_documents=False)

    assert result.tool_names == ["clock"]
    assert "T" in result.tool_calls[0]["output"]
    assert "clock" in llm.calls[1][0].content
    assert result.prompt_version == "agent-answer-v1"


async def test_graph_answers_directly_when_documents_off(
    fake_embeddings: FakeEmbeddingProvider,
) -> None:
    llm = FakeLLMProvider(replies=[PLAN_ANSWER, "Hello."])
    agent = await _agent(llm, fake_embeddings, chunks=[_chunk()])

    result = await agent.run(question="hi", history=[], use_documents=False)

    assert result.mode == "chat"
    assert result.retrieved_chunks == 0
    assert result.nodes_visited == ["plan", "generate_answer"]
    assert result.prompt_version == "chat-system-v1"
    assert len(llm.calls) == 2


async def test_graph_clamps_retrieve_when_documents_disabled(
    fake_embeddings: FakeEmbeddingProvider,
) -> None:
    llm = FakeLLMProvider(replies=[PLAN_RETRIEVE, "I will not search."])
    agent = await _agent(llm, fake_embeddings, chunks=[_chunk()])

    result = await agent.run(question="how many days?", history=[], use_documents=False)

    assert "retrieve" not in result.nodes_visited
    assert result.retrieved_chunks == 0
    assert result.nodes_visited == ["plan", "generate_answer"]


async def test_graph_save_note_interrupts_until_approved(
    fake_embeddings: FakeEmbeddingProvider, tmp_path: Path
) -> None:
    notes = tmp_path / "notes.jsonl"
    llm = FakeLLMProvider(replies=[PLAN_NOTE, "Saved."])
    agent = await _agent(llm, fake_embeddings, notes_path=notes)

    paused = await agent.run(
        question="remember to buy milk", history=[], use_documents=False, thread_id="hitl"
    )
    assert paused.pending_approval is not None
    assert paused.pending_approval["tool"] == "save_note"
    assert paused.tool_names == []
    assert not notes.exists()

    done = await agent.resume("hitl", approved=True)
    assert done.pending_approval is None
    assert done.tool_names == ["save_note"]
    assert done.tool_calls[0]["ok"] == "true"
    assert "Saved note" in done.tool_calls[0]["output"]
    assert "Buy milk" in notes.read_text(encoding="utf-8")


async def test_graph_save_note_reject_skips_write(
    fake_embeddings: FakeEmbeddingProvider, tmp_path: Path
) -> None:
    notes = tmp_path / "notes.jsonl"
    llm = FakeLLMProvider(replies=[PLAN_NOTE, "Not saved."])
    agent = await _agent(llm, fake_embeddings, notes_path=notes)

    await agent.run(question="remember this", history=[], use_documents=False, thread_id="nope")
    done = await agent.resume("nope", approved=False)
    assert done.tool_calls[0]["ok"] == "false"
    assert "rejected" in done.tool_calls[0]["output"].lower()
    assert not notes.exists()


async def test_graph_garbled_plan_retrieves_when_documents_on(
    fake_embeddings: FakeEmbeddingProvider,
) -> None:
    llm = FakeLLMProvider(reply="Twenty five days [Source 1].")
    agent = await _agent(llm, fake_embeddings, chunks=[_chunk()])

    result = await agent.run(question="leave days?", history=[], use_documents=True)

    assert "retrieve" in result.nodes_visited
    assert result.mode == "rag"
