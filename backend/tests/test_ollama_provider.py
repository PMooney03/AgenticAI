"""OllamaProvider tests with the network mocked out; no Ollama needed."""

import httpx
import pytest
from langchain_core.messages import AIMessage

from app.llm import ChatMessage, LLMUnavailableError, OllamaProvider
from app.llm.ollama import _text_content, _to_langchain


def _provider() -> OllamaProvider:
    return OllamaProvider(base_url="http://ollama.test:11434/", model="qwen2.5:14b")


def test_messages_are_converted_to_langchain_types() -> None:
    converted = _to_langchain(
        [
            ChatMessage(role="system", content="s"),
            ChatMessage(role="user", content="u"),
            ChatMessage(role="assistant", content="a"),
        ]
    )
    assert [m.type for m in converted] == ["system", "human", "ai"]
    assert [m.content for m in converted] == ["s", "u", "a"]


def test_text_content_handles_string_and_blocks() -> None:
    assert _text_content(AIMessage(content="plain")) == "plain"
    blocks = AIMessage(content=[{"type": "text", "text": "a"}, {"type": "text", "text": "b"}])
    assert _text_content(blocks) == "ab"


class _StubChatModel:
    """Stands in for ``ChatOllama`` (a pydantic model, so it cannot be monkeypatched)."""

    def __init__(self, response: AIMessage | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.received: list[object] = []

    async def ainvoke(self, messages: object) -> AIMessage:
        self.received.append(messages)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


async def test_chat_maps_langchain_response(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider()
    stub = _StubChatModel(
        AIMessage(
            content="42",
            usage_metadata={"input_tokens": 10, "output_tokens": 1, "total_tokens": 11},
            response_metadata={"model": "qwen2.5:14b", "done_reason": "stop"},
        )
    )
    monkeypatch.setattr(provider, "_client", stub)
    result = await provider.chat([ChatMessage(role="user", content="6*7?")])

    assert len(stub.received) == 1

    assert result.content == "42"
    assert result.model == "qwen2.5:14b"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 1
    assert result.latency_ms >= 0
    assert result.raw_metadata["done_reason"] == "stop"


async def test_chat_wraps_client_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider()
    monkeypatch.setattr(provider, "_client", _StubChatModel(error=ConnectionError("refused")))
    with pytest.raises(LLMUnavailableError, match="qwen2.5:14b"):
        await provider.chat([ChatMessage(role="user", content="hi")])


def _mock_tags(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    real_client = httpx.AsyncClient

    def patched(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = handler
        return real_client(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", patched)


async def test_health_true_when_model_is_pulled(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:14b"}]})

    _mock_tags(monkeypatch, httpx.MockTransport(handler))
    assert await _provider().health() is True


async def test_health_false_when_model_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "llama3.2:latest"}]})

    _mock_tags(monkeypatch, httpx.MockTransport(handler))
    assert await _provider().health() is False


async def test_health_false_when_server_down(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    _mock_tags(monkeypatch, httpx.MockTransport(handler))
    assert await _provider().health() is False


async def test_health_matches_untagged_model_to_latest(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "llama3.2:latest"}]})

    _mock_tags(monkeypatch, httpx.MockTransport(handler))
    provider = OllamaProvider(base_url="http://ollama.test:11434", model="llama3.2")
    assert await provider.health() is True
