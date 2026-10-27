"""LLM_PROVIDER=fake / EMBEDDING_PROVIDER=fake without dependency_overrides.

This is the Compose smoke path: the app factory wires fakes from settings, so CI can
`up` the backend image with no Ollama and no Qdrant container.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_settings
from app.main import create_app


@pytest.fixture
def fake_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_provider="fake",
        embedding_provider="fake",
        qdrant_url=":memory:",
        data_dir=tmp_path / "data",
        log_level="WARNING",
    )


@pytest.fixture
def fake_mode_client(fake_settings: Settings) -> Iterator[TestClient]:
    application = create_app(fake_settings)
    application.dependency_overrides[get_settings] = lambda: fake_settings
    with TestClient(application) as client:
        yield client
    application.dependency_overrides.clear()


def test_fake_mode_health_is_ok_without_ollama(fake_mode_client: TestClient) -> None:
    response = fake_mode_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ollama"]["reachable"] is True
    assert body["ollama"]["model"] == "fake-model"
    assert body["embeddings"]["reachable"] is True
    assert body["embeddings"]["model"] == "fake-embed"
    assert body["qdrant"]["reachable"] is True
    assert body["qdrant"]["url"] == ":memory:"


def test_fake_mode_chat_answers_without_documents(fake_mode_client: TestClient) -> None:
    response = fake_mode_client.post("/chat", json={"message": "hello", "use_documents": False})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["pending_approval"] is None
