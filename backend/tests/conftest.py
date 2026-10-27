"""Shared fixtures.

No test here talks to Ollama. The LLM dependency is overridden with ``FakeLLMProvider``
and settings are constructed explicitly so the developer's ``.env`` cannot leak in.
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import get_llm_provider
from app.llm import FakeLLMProvider
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        ollama_base_url="http://ollama.test:11434",
        ollama_model="test-model:latest",
        log_level="WARNING",
    )


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider(reply="Hello from the fake model.", model="test-model:latest")


@pytest.fixture
def app(settings: Settings, fake_llm: FakeLLMProvider) -> Iterator[FastAPI]:
    application = create_app(settings)
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_llm_provider] = lambda: fake_llm
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
