from fastapi.testclient import TestClient

from app.llm import FakeLLMProvider
from app.observability.metrics import ChatObservation, MetricsStore, normalise_route


def test_normalise_route_collapses_ids() -> None:
    assert normalise_route("/agent/trace/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa") == "/agent/trace/{id}"
    assert normalise_route("/health") == "/health"
    assert normalise_route("/") == "/"


def test_metrics_store_aggregates_without_content() -> None:
    store = MetricsStore()
    store.observe_http(method="POST", path="/chat", status_code=200)
    store.observe_chat(
        ChatObservation(
            mode="rag",
            llm_ms=10,
            retrieval_ms=4,
            retrieved_chunks=2,
            cited_sources=1,
            prompt_tokens=8,
            completion_tokens=3,
            tools=[],
            paused=False,
            refused=False,
            citation_rate=0.5,
            groundedness=0.8,
        )
    )
    snap = store.snapshot()
    dumped = str(snap).lower()
    assert snap["chats"] == 1
    assert snap["chats_rag"] == 1
    assert snap["citation_rate_avg"] == 0.5
    assert snap["groundedness_avg"] == 0.8
    assert snap["llm"]["count"] == 1
    assert "employees" not in dumped
    assert "leave" not in dumped


def test_paused_chat_is_not_counted_complete_until_resume() -> None:
    store = MetricsStore()
    paused = ChatObservation(
        mode="chat",
        llm_ms=1,
        retrieval_ms=0,
        retrieved_chunks=0,
        cited_sources=0,
        prompt_tokens=None,
        completion_tokens=None,
        tools=[],
        paused=True,
        refused=False,
        citation_rate=None,
        groundedness=None,
    )
    store.observe_chat(paused)
    store.observe_chat(
        ChatObservation(
            mode="chat",
            llm_ms=2,
            retrieval_ms=0,
            retrieved_chunks=0,
            cited_sources=0,
            prompt_tokens=4,
            completion_tokens=2,
            tools=["save_note"],
            paused=False,
            refused=False,
            citation_rate=None,
            groundedness=1.0,
        ),
        new=False,
    )
    store.observe_approval(approved=True)
    snap = store.snapshot()
    assert snap["chats"] == 1
    assert snap["chats_paused"] == 1
    assert snap["chats_completed"] == 1
    assert snap["approvals_approved"] == 1
    assert snap["tools"] == {"save_note": 1}


def test_metrics_endpoint_tracks_a_chat(client: TestClient, fake_llm: FakeLLMProvider) -> None:
    fake_llm.replies = [
        '{"action": "answer", "tool_name": null, "tool_args": {}}',
        "Hello from the fake model.",
    ]
    chat = client.post("/chat", json={"message": "Hello there.", "use_documents": False})
    assert chat.status_code == 200
    body = client.get("/metrics").json()
    assert body["chats"] >= 1
    assert body["chats_completed"] >= 1
    # Snapshot is built inside the handler, so this GET is not in the count yet.
    assert body["http_requests"] >= 1
    assert "POST /chat" in body["routes"]
