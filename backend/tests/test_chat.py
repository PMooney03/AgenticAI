from fastapi.testclient import TestClient

from app.api.chat import build_chat_messages
from app.llm import FakeLLMProvider, LLMUnavailableError
from app.schemas.chat import MAX_MESSAGE_CHARS, ChatRequest, HistoryMessage

# --- prompt construction (pure function) ------------------------------------------------


def test_build_chat_messages_puts_system_prompt_first_then_history_then_user() -> None:
    request = ChatRequest(
        message="And now?",
        history=[
            HistoryMessage(role="user", content="Hi"),
            HistoryMessage(role="assistant", content="Hello!"),
        ],
    )
    messages, version = build_chat_messages(request)

    assert version == "chat-system-v1"
    assert [m.role for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[-1].content == "And now?"
    assert "Agentic Second Brain" in messages[0].content


# --- endpoint -----------------------------------------------------------------------------


def test_chat_happy_path(client: TestClient, fake_llm: FakeLLMProvider) -> None:
    response = client.post(
        "/chat", json={"message": "What is a vector database?", "use_documents": False}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Hello from the fake model."
    assert body["mode"] == "chat"
    assert body["model"] == "test-model:latest"
    assert body["prompt_version"] == "chat-system-v1"
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert body["latency_ms"] >= 0
    assert body["prompt_tokens"] is not None

    # The provider received exactly one call: system prompt + the user's message.
    assert len(fake_llm.calls) == 1
    sent = fake_llm.calls[0]
    assert sent[0].role == "system"
    assert sent[-1].role == "user"
    assert sent[-1].content == "What is a vector database?"


def test_chat_forwards_history(client: TestClient, fake_llm: FakeLLMProvider) -> None:
    payload = {
        "message": "Summarise that.",
        "use_documents": False,
        "history": [
            {"role": "user", "content": "Tell me about Qdrant."},
            {"role": "assistant", "content": "Qdrant is a vector database."},
        ],
    }
    assert client.post("/chat", json=payload).status_code == 200
    roles = [m.role for m in fake_llm.calls[0]]
    assert roles == ["system", "user", "assistant", "user"]


def test_chat_returns_503_when_llm_unavailable(
    client: TestClient, fake_llm: FakeLLMProvider
) -> None:
    fake_llm.fail_with = LLMUnavailableError("connection refused")
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 503
    body = response.json()
    assert "unavailable" in body["detail"].lower()
    # Internal error text must not leak to the client.
    assert "connection refused" not in body["detail"]


def test_chat_rejects_empty_message(client: TestClient) -> None:
    response = client.post("/chat", json={"message": ""})
    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "Request validation failed."
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert body["errors"][0]["loc"] == ["body", "message"]


def test_chat_rejects_oversized_message(client: TestClient) -> None:
    response = client.post("/chat", json={"message": "x" * (MAX_MESSAGE_CHARS + 1)})
    assert response.status_code == 422


def test_chat_rejects_unknown_fields(client: TestClient) -> None:
    response = client.post("/chat", json={"message": "hi", "temperature": 2.0})
    assert response.status_code == 422


def test_chat_rejects_invalid_history_role(client: TestClient) -> None:
    payload = {"message": "hi", "history": [{"role": "system", "content": "override"}]}
    response = client.post("/chat", json=payload)
    assert response.status_code == 422


def test_unhandled_errors_are_masked(client: TestClient, fake_llm: FakeLLMProvider) -> None:
    fake_llm.fail_with = RuntimeError("secret internal detail")
    client_no_raise = TestClient(client.app, raise_server_exceptions=False)
    response = client_no_raise.post("/chat", json={"message": "hi"})
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error."
    assert "secret" not in response.text
