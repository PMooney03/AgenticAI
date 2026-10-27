"""Deterministic in-memory provider for tests and offline development.

Lives in ``app`` (not ``tests``) so it can also back a ``LLM_PROVIDER=fake`` mode later,
e.g. for CI smoke tests of the full stack without a model runtime.
"""

from app.llm.base import ChatMessage, LLMResult, LLMUnavailableError


class FakeLLMProvider:
    """Echoes a canned reply and records every call it receives."""

    def __init__(
        self,
        *,
        reply: str = "This is a fake answer.",
        model: str = "fake-model",
        healthy: bool = True,
        fail_with: Exception | None = None,
    ) -> None:
        self.reply = reply
        self._model = model
        self.healthy = healthy
        self.fail_with = fail_with
        self.calls: list[list[ChatMessage]] = []

    @property
    def model_name(self) -> str:
        return self._model

    async def chat(self, messages: list[ChatMessage]) -> LLMResult:
        self.calls.append(list(messages))
        if self.fail_with is not None:
            raise self.fail_with
        if not self.healthy:
            raise LLMUnavailableError("fake provider marked unhealthy")
        return LLMResult(
            content=self.reply,
            model=self._model,
            latency_ms=1,
            prompt_tokens=sum(len(m.content.split()) for m in messages),
            completion_tokens=len(self.reply.split()),
        )

    async def health(self) -> bool:
        return self.healthy
