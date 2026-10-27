"""Shared fixtures.

No test here talks to Ollama or a Qdrant server. Leaf dependencies are overridden:
- LLM        -> FakeLLMProvider
- embeddings -> FakeEmbeddingProvider (deterministic hashed bag-of-words)
- Qdrant     -> QdrantVectorStore(location=":memory:") - real client code, in-process
- registry   -> SQLite file under the test's tmp_path
Settings are constructed explicitly so the developer's ``.env`` cannot leak in.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import (
    get_document_registry,
    get_embedding_provider,
    get_llm_provider,
    get_vector_store,
)
from app.embeddings import FakeEmbeddingProvider
from app.ingestion import DocumentRegistry
from app.llm import FakeLLMProvider
from app.main import create_app
from app.retrieval import QdrantVectorStore
from tests.helpers import make_pdf  # noqa: F401 - re-exported for convenience


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        ollama_base_url="http://ollama.test:11434",
        ollama_model="test-model:latest",
        embedding_model="fake-embed",
        qdrant_url=":memory:",
        qdrant_collection="test_documents",
        data_dir=tmp_path / "data",
        max_upload_mb=1,
        chunk_size_tokens=60,
        chunk_overlap_tokens=10,
        log_level="WARNING",
    )


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider(reply="Hello from the fake model.", model="test-model:latest")


@pytest.fixture
def fake_embeddings() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def vector_store(settings: Settings) -> QdrantVectorStore:
    return QdrantVectorStore(location=":memory:", collection=settings.qdrant_collection)


@pytest.fixture
def registry(settings: Settings) -> DocumentRegistry:
    return DocumentRegistry(settings.registry_db_path)


@pytest.fixture
def app(
    settings: Settings,
    fake_llm: FakeLLMProvider,
    fake_embeddings: FakeEmbeddingProvider,
    vector_store: QdrantVectorStore,
    registry: DocumentRegistry,
) -> Iterator[FastAPI]:
    application = create_app(settings)
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_llm_provider] = lambda: fake_llm
    application.dependency_overrides[get_embedding_provider] = lambda: fake_embeddings
    application.dependency_overrides[get_vector_store] = lambda: vector_store
    application.dependency_overrides[get_document_registry] = lambda: registry
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
