import pytest
from pydantic import ValidationError

from app.config import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_defaults_point_at_local_ollama() -> None:
    s = _settings()
    assert s.ollama_base_url_str == "http://localhost:11434"
    assert s.ollama_model == "qwen2.5:14b"
    assert s.log_level == "INFO"


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434/")
    monkeypatch.setenv("OLLAMA_MODEL", "  llama3.2  ")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s = _settings()
    assert s.ollama_base_url_str == "http://host.docker.internal:11434"
    assert s.ollama_model == "llama3.2"
    assert s.log_level == "DEBUG"


def test_blank_model_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(ollama_model="   ")


def test_invalid_url_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(ollama_base_url="not-a-url")


def test_invalid_log_level_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(log_level="LOUD")


def test_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _settings(ollama_timeout_seconds=0)
