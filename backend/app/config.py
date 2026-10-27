"""Application configuration.

All runtime configuration comes from environment variables (optionally loaded from a
``.env`` file at the repository root). Nothing secret is ever hardcoded here, and the
settings object is the single place the rest of the app reads configuration from.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> repository root is two levels up from ``backend``.
_REPO_ROOT = Path(__file__).resolve().parents[2]

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Typed view of the environment."""

    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Agentic Second Brain"
    app_version: str = "0.1.0"
    log_level: LogLevel = "INFO"

    # --- Ollama -------------------------------------------------------------
    ollama_base_url: HttpUrl = Field(default=HttpUrl("http://localhost:11434"))
    ollama_model: str = "qwen2.5:14b"
    ollama_timeout_seconds: float = Field(default=120.0, gt=0)
    ollama_temperature: float = Field(default=0.2, ge=0.0, le=2.0)

    @field_validator("ollama_model")
    @classmethod
    def _model_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("OLLAMA_MODEL must not be empty")
        return value

    @property
    def ollama_base_url_str(self) -> str:
        """Base URL as a plain string without a trailing slash (what clients expect)."""
        return str(self.ollama_base_url).rstrip("/")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    Cached so the environment is read once. Tests can call ``get_settings.cache_clear()``
    or override the FastAPI dependency to inject custom settings.
    """
    return Settings()
