"""Versioned prompts.

Every system prompt is a :class:`PromptTemplate` with an explicit ``version`` ID
(e.g. ``chat-system-v1``). Code never embeds large prompt strings inline; it asks the
registry for a prompt by name and the version used is logged with each request.
"""

from app.prompts.registry import PromptNotFoundError, PromptTemplate, get_prompt, list_prompts

__all__ = ["PromptNotFoundError", "PromptTemplate", "get_prompt", "list_prompts"]
