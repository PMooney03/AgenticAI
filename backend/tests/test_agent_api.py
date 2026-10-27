from fastapi.testclient import TestClient

from app.dependencies import (
    get_document_registry,
    get_embedding_provider,
    get_llm_provider,
    get_settings,
    get_vector_store,
)
from app.llm import FakeLLMProvider
from app.main import create_app

PLAN_TOOL = (
    '{"action": "tool", "tool_name": "calculator", "tool_args": {"expression": "12 * (3 + 4)"}}'
)
PLAN_CLOCK = '{"action": "tool", "tool_name": "clock", "tool_args": {}}'


def test_list_tools(client: TestClient) -> None:
    response = client.get("/agent/tools")
    assert response.status_code == 200
    body = response.json()
    names = [tool["name"] for tool in body["tools"]]
    assert names == ["calculator", "clock", "save_note"]
    by_name = {tool["name"]: tool for tool in body["tools"]}
    assert all(tool["source"] == "mcp" for tool in body["tools"])
    assert by_name["calculator"]["read_only"] is True
    assert by_name["calculator"]["requires_approval"] is False
    assert by_name["save_note"]["read_only"] is False
    assert by_name["save_note"]["requires_approval"] is True


def test_trace_404_for_unknown_request(client: TestClient) -> None:
    response = client.get("/agent/trace/does-not-exist")
    assert response.status_code == 404
    assert "trace" in response.json()["detail"].lower()


def test_chat_calculator_path_writes_trace(client: TestClient, fake_llm: FakeLLMProvider) -> None:
    fake_llm.replies = [PLAN_TOOL, "The product is 84."]
    response = client.post(
        "/chat", json={"message": "what is 12 * (3 + 4)?", "use_documents": False}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "chat"
    assert body["prompt_version"] == "agent-answer-v1"
    assert any("calculator" in step["label"] for step in body["workflow"])
    assert body["retrieval"] is None

    trace = client.get(f"/agent/trace/{body['request_id']}")
    assert trace.status_code == 200
    payload = trace.json()
    assert payload["request_id"] == body["request_id"]
    assert "call_tool" in payload["nodes_visited"]
    assert payload["tools"] == ["calculator"]
    assert payload["retrieved_chunks"] == 0
    # No document text, question, or planner JSON in the inspectable trace.
    dumped = trace.text.lower()
    assert "12 * (3 + 4)" not in dumped
    assert "handbook" not in dumped


def test_chat_clock_path_goes_through_mcp(client: TestClient, fake_llm: FakeLLMProvider) -> None:
    fake_llm.replies = [PLAN_CLOCK, "The local time is shown above."]
    response = client.post("/chat", json={"message": "what time is it?", "use_documents": False})
    assert response.status_code == 200, response.text
    body = response.json()
    assert any("clock" in step["label"] for step in body["workflow"])
    trace = client.get(f"/agent/trace/{body['request_id']}")
    assert trace.json()["tools"] == ["clock"]


PLAN_NOTE = (
    '{"action": "tool", "tool_name": "save_note", '
    '"tool_args": {"text": "Buy milk", "title": "todo"}}'
)


def test_chat_save_note_pauses_then_writes_on_approve(
    client: TestClient, fake_llm: FakeLLMProvider, settings
) -> None:
    fake_llm.replies = [PLAN_NOTE, "Saved to your notebook."]
    paused = client.post("/chat", json={"message": "remember to buy milk", "use_documents": False})
    assert paused.status_code == 200, paused.text
    body = paused.json()
    pending = body["pending_approval"]
    assert pending["tool"] == "save_note"
    assert "notebook" in pending["description"].lower()
    assert "Buy milk" in pending["preview"]
    assert any(step["label"] == "Waiting for approval" for step in body["workflow"])
    notes = settings.notes_path
    assert not notes.exists()

    done = client.post(f"/agent/runs/{body['request_id']}/decision", json={"approved": True})
    assert done.status_code == 200, done.text
    finished = done.json()
    assert finished["pending_approval"] is None
    assert any("save_note" in step["label"] for step in finished["workflow"])
    assert "Buy milk" in notes.read_text(encoding="utf-8")
    dumped = client.get(f"/agent/trace/{body['request_id']}").text.lower()
    assert "buy milk" not in dumped


def test_chat_save_note_reject_does_not_write(
    client: TestClient, fake_llm: FakeLLMProvider, settings
) -> None:
    fake_llm.replies = [PLAN_NOTE, "Nothing was written."]
    paused = client.post("/chat", json={"message": "remember to buy milk", "use_documents": False})
    body = paused.json()
    done = client.post(f"/agent/runs/{body['request_id']}/decision", json={"approved": False})
    assert done.status_code == 200, done.text
    assert any("Rejected" in step["label"] for step in done.json()["workflow"])
    assert not settings.notes_path.exists()


def test_decision_404_without_pending(client: TestClient) -> None:
    response = client.post("/agent/runs/does-not-exist/decision", json={"approved": True})
    assert response.status_code == 404


def test_approval_survives_app_restart(
    settings,
    fake_llm: FakeLLMProvider,
    fake_embeddings,
    vector_store,
    registry,
) -> None:
    fake_llm.replies = [PLAN_NOTE, "Saved after restart."]

    def _app():
        application = create_app(settings)
        application.dependency_overrides[get_settings] = lambda: settings
        application.dependency_overrides[get_llm_provider] = lambda: fake_llm
        application.dependency_overrides[get_embedding_provider] = lambda: fake_embeddings
        application.dependency_overrides[get_vector_store] = lambda: vector_store
        application.dependency_overrides[get_document_registry] = lambda: registry
        return application

    with TestClient(_app()) as first:
        paused = first.post(
            "/chat", json={"message": "remember to buy milk", "use_documents": False}
        )
        assert paused.status_code == 200, paused.text
        request_id = paused.json()["request_id"]
        assert paused.json()["pending_approval"]["tool"] == "save_note"
        assert not settings.notes_path.exists()

    with TestClient(_app()) as second:
        done = second.post(f"/agent/runs/{request_id}/decision", json={"approved": True})
        assert done.status_code == 200, done.text
        assert done.json()["pending_approval"] is None
        assert "Buy milk" in settings.notes_path.read_text(encoding="utf-8")
