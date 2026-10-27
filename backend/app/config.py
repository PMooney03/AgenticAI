"""Application configuration.

All runtime configuration comes from environment variables (optionally loaded from a
``.env`` file at the repository root). Nothing secret is ever hardcoded here, and the
settings object is the single place the rest of the app reads configuration from.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
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

    # --- Embeddings (served by the same Ollama instance) -------------------
    embedding_model: str = "nomic-embed-text"
    embedding_batch_size: int = Field(default=32, ge=1, le=256)

    # --- Qdrant -------------------------------------------------------------
    # A URL for the Docker service, or ":memory:" for an in-process store (tests).
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "documents"
    qdrant_api_key: SecretStr | None = None

    # --- Ingestion ----------------------------------------------------------
    data_dir: Path = _REPO_ROOT / "data"
    max_upload_mb: int = Field(default=20, ge=1, le=500)
    chunk_size_tokens: int = Field(default=400, ge=50, le=4000)
    chunk_overlap_tokens: int = Field(default=60, ge=0, le=1000)

    # --- Retrieval ----------------------------------------------------------
    retrieval_top_k: int = Field(default=4, ge=1, le=20)
    retrieval_score_threshold: float = Field(default=0.0, ge=-1.0, le=1.0)

    @field_validator("ollama_model", "embedding_model", "qdrant_collection")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def _overlap_smaller_than_chunk(self) -> "Settings":
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_SIZE_TOKENS")
        return self

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def registry_db_path(self) -> Path:
        return self.data_dir / "registry.db"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

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
