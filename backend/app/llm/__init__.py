"""LLM provider abstraction.

The rest of the application only depends on :class:`~app.llm.base.LLMProvider`.
Concrete providers (Ollama today; others later) live alongside it.
"""

from app.llm.base import ChatMessage, LLMProvider, LLMResult, LLMUnavailableError, Role
from app.llm.fake import FakeLLMProvider
from app.llm.ollama import OllamaProvider

__all__ = [
    "ChatMessage",
    "FakeLLMProvider",
    "LLMProvider",
    "LLMResult",
    "LLMUnavailableError",
    "OllamaProvider",
    "Role",
]
