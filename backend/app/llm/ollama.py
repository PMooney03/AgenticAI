"""Ollama-backed :class:`LLMProvider`.

LangChain's ``ChatOllama`` is used purely as the HTTP client for Ollama's chat API. It
gives us a vendor-neutral message format, retries/streaming support later, and - from
Phase 4 - native tool calling and structured output. The orchestration logic stays in our
own code; LangChain is a thin adapter here, not the architecture.
"""

import logging
import time
from collections.abc import Sequence

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.llm.base import ChatMessage, LLMResult, LLMUnavailableError

logger = logging.getLogger(__name__)


def _to_langchain(messages: Sequence[ChatMessage]) -> list[BaseMessage]:
    converted: list[BaseMessage] = []
    for message in messages:
        if message.role == "system":
            converted.append(SystemMessage(content=message.content))
        elif message.role == "user":
            converted.append(HumanMessage(content=message.content))
        else:
            converted.append(AIMessage(content=message.content))
    return converted


def _text_content(message: AIMessage) -> str:
    """``AIMessage.content`` may be a string or a list of content blocks."""
    content = message.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)


class OllamaProvider:
    """Talks to a local Ollama server."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        temperature: float = 0.2,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._client = ChatOllama(
            model=model,
            base_url=self._base_url,
            temperature=temperature,
            client_kwargs={"timeout": timeout_seconds},
        )

    @property
    def model_name(self) -> str:
        return self._model

    async def chat(self, messages: list[ChatMessage]) -> LLMResult:
        started = time.perf_counter()
        try:
            response = await self._client.ainvoke(_to_langchain(messages))
        except Exception as exc:  # noqa: BLE001 - normalise any client failure
            raise LLMUnavailableError(
                f"Ollama request failed for model '{self._model}' at {self._base_url}: {exc}"
            ) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        usage = response.usage_metadata or {}
        metadata = dict(response.response_metadata or {})
        return LLMResult(
            content=_text_content(response),
            model=str(metadata.get("model") or self._model),
            latency_ms=latency_ms,
            prompt_tokens=usage.get("input_tokens"),
            completion_tokens=usage.get("output_tokens"),
            raw_metadata=metadata,
        )

    async def health(self) -> bool:
        """Reachable *and* the configured model is pulled locally."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
                models = response.json().get("models", [])
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ollama_health_check_failed", extra={"error": str(exc)})
            return False

        names = {m.get("name", "") for m in models}
        # Ollama lists "qwen2.5:14b"; a configured "qwen2.5" should match "qwen2.5:latest".
        wanted = self._model if ":" in self._model else f"{self._model}:latest"
        return wanted in names
