"""Prompt registry.

A prompt is identified by a stable *name* (``"chat-system"``) and resolves to the current
*version* (``"chat-system-v1"``). Bumping a prompt means adding a new module/version and
pointing the registry at it, which keeps old versions available for evaluation and makes
every logged ``prompt_version`` traceable to exact text.
"""

from dataclasses import dataclass
from string import Formatter


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    name: str
    version: str
    template: str
    description: str = ""

    @property
    def variables(self) -> frozenset[str]:
        """Placeholder names used by the template (``{like_this}``)."""
        return frozenset(
            field for _, field, _, _ in Formatter().parse(self.template) if field is not None
        )

    def render(self, **values: str) -> str:
        missing = self.variables - values.keys()
        if missing:
            raise KeyError(f"Prompt '{self.version}' missing variables: {sorted(missing)}")
        return self.template.format(**values)


class PromptNotFoundError(KeyError):
    """Raised when no prompt is registered under the requested name."""


_REGISTRY: dict[str, PromptTemplate] = {}


def register(prompt: PromptTemplate) -> PromptTemplate:
    if prompt.name in _REGISTRY:
        raise ValueError(f"Prompt '{prompt.name}' is already registered")
    _REGISTRY[prompt.name] = prompt
    return prompt


def get_prompt(name: str) -> PromptTemplate:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise PromptNotFoundError(name) from exc


def list_prompts() -> list[PromptTemplate]:
    return sorted(_REGISTRY.values(), key=lambda p: p.name)


# Importing the version modules registers them. Kept at the bottom to avoid cycles.
from app.prompts import chat_system_v1, rag_system_v1  # noqa: E402, F401
