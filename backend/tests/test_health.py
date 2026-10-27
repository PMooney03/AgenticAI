from fastapi.testclient import TestClient

from app.llm import FakeLLMProvider


def test_health_ok_when_llm_reachable(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "Agentic Second Brain"
    assert body["ollama"] == {
        "reachable": True,
        "model": "test-model:latest",
        "base_url": "http://ollama.test:11434",
    }
    assert body["embeddings"]["reachable"] is True
    assert body["qdrant"]["reachable"] is True


def test_health_degraded_when_llm_unreachable(
    client: TestClient, fake_llm: FakeLLMProvider
) -> None:
    fake_llm.healthy = False
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["ollama"]["reachable"] is False


def test_every_response_carries_a_request_id(client: TestClient) -> None:
    response = client.get("/health")
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32  # uuid4().hex


def test_incoming_request_id_is_honoured(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "frontend-abc-123"})
    assert response.headers["X-Request-ID"] == "frontend-abc-123"


def test_oversized_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "x" * 500})
    assert response.headers["X-Request-ID"] != "x" * 500
    assert len(response.headers["X-Request-ID"]) == 32
