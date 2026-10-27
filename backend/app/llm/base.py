"""Provider-agnostic LLM interface.

Why an abstraction?
    Routes, prompts and (later) LangGraph nodes should not know *which* model runtime they
    are talking to. Keeping the surface tiny (one ``chat`` call, one ``health`` call) makes
    it trivial to add another provider, e.g. a hosted model, without touching business
    logic, and lets tests inject a fake implementation.
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A single message in a conversation, independent of any vendor SDK."""

    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class LLMResult:
    """What a provider returns from a chat completion."""

    content: str
    model: str
    latency_ms: int
    # Token counts are best-effort: not every runtime reports them.
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    raw_metadata: dict = field(default_factory=dict)


class LLMUnavailableError(RuntimeError):
    """Raised when the model runtime cannot be reached or fails to respond."""


@runtime_checkable
class LLMProvider(Protocol):
    """The only contract the application relies on for text generation."""

    @property
    def model_name(self) -> str:
        """Identifier of the model being served (for logging and responses)."""
        ...

    async def chat(self, messages: list[ChatMessage]) -> LLMResult:
        """Generate the next assistant message for the given conversation."""
        ...

    async def health(self) -> bool:
        """Return True if the runtime is reachable and the model is available."""
        ...
