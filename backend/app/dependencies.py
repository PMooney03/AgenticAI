"""FastAPI dependency seams.

Routes depend on these functions rather than on concrete classes. Tests replace them via
``app.dependency_overrides`` to inject fakes without a running Ollama.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.config import Settings, get_settings
from app.llm import LLMProvider, OllamaProvider

SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def _build_ollama_provider(
    base_url: str, model: str, timeout_seconds: float, temperature: float
) -> OllamaProvider:
    # Cached per unique config so the HTTP client is reused across requests.
    return OllamaProvider(
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )


def get_llm_provider(settings: SettingsDep) -> LLMProvider:
    return _build_ollama_provider(
        settings.ollama_base_url_str,
        settings.ollama_model,
        settings.ollama_timeout_seconds,
        settings.ollama_temperature,
    )


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]
