"""LocalEmbeddingProvider with the network mocked; FakeEmbeddingProvider sanity checks."""

import json
import math

import httpx
import pytest

from app.embeddings import EmbeddingUnavailableError, FakeEmbeddingProvider, LocalEmbeddingProvider


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real_client = httpx.AsyncClient

    def patched(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", patched)


async def test_embed_documents_batches_and_prefixes_for_nomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        payload = json.loads(request.content)
        assert payload["model"] == "nomic-embed-text"
        seen.append(payload["input"])
        return httpx.Response(200, json={"embeddings": [[1.0, 0.0]] * len(payload["input"])})

    _patch_transport(monkeypatch, handler)
    provider = LocalEmbeddingProvider(
        base_url="http://ollama.test:11434", model="nomic-embed-text", batch_size=2
    )
    vectors = await provider.embed_documents(["a", "b", "c"])

    assert vectors == [[1.0, 0.0]] * 3
    assert seen == [["search_document: a", "search_document: b"], ["search_document: c"]]


async def test_embed_query_uses_query_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["input"] == ["search_query: hello"]
        return httpx.Response(200, json={"embeddings": [[0.5, 0.5]]})

    _patch_transport(monkeypatch, handler)
    provider = LocalEmbeddingProvider(base_url="http://ollama.test:11434", model="nomic-embed-text")
    assert await provider.embed_query("hello") == [0.5, 0.5]


async def test_no_prefix_for_other_models(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["input"] == ["hello"]
        return httpx.Response(200, json={"embeddings": [[1.0]]})

    _patch_transport(monkeypatch, handler)
    provider = LocalEmbeddingProvider(base_url="http://ollama.test:11434", model="bge-m3")
    assert await provider.embed_query("hello") == [1.0]


async def test_server_error_becomes_embedding_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, lambda req: httpx.Response(500, text="boom"))
    provider = LocalEmbeddingProvider(base_url="http://ollama.test:11434", model="nomic-embed-text")
    with pytest.raises(EmbeddingUnavailableError, match="nomic-embed-text"):
        await provider.embed_query("x")


async def test_malformed_response_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, lambda req: httpx.Response(200, json={"embeddings": []}))
    provider = LocalEmbeddingProvider(base_url="http://ollama.test:11434", model="nomic-embed-text")
    with pytest.raises(EmbeddingUnavailableError, match="malformed"):
        await provider.embed_documents(["x"])


async def test_empty_input_short_circuits() -> None:
    provider = LocalEmbeddingProvider(base_url="http://ollama.test:11434", model="nomic-embed-text")
    assert await provider.embed_documents([]) == []


async def test_health_checks_model_is_pulled(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(
        monkeypatch,
        lambda req: httpx.Response(200, json={"models": [{"name": "nomic-embed-text:latest"}]}),
    )
    provider = LocalEmbeddingProvider(base_url="http://ollama.test:11434", model="nomic-embed-text")
    assert await provider.health() is True


async def test_fake_embeddings_are_unit_norm_and_similarity_tracks_overlap() -> None:
    fake = FakeEmbeddingProvider()
    a, b, c = await fake.embed_documents(
        ["revenue grew strongly", "revenue grew a little", "bake the sponge cake"]
    )

    def dot(x: list[float], y: list[float]) -> float:
        return sum(p * q for p, q in zip(x, y, strict=True))

    assert math.isclose(dot(a, a), 1.0, abs_tol=1e-9)
    assert dot(a, b) > dot(a, c)
