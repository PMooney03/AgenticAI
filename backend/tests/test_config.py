import pytest
from pydantic import ValidationError

from app.config import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_defaults_point_at_local_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("OLLAMA_BASE_URL", "OLLAMA_MODEL", "LOG_LEVEL", "CORS_ORIGINS"):
        monkeypatch.delenv(key, raising=False)
    s = _settings()
    assert s.ollama_base_url_str == "http://localhost:11434"
    assert s.ollama_model == "qwen2.5:14b"
    assert s.log_level == "INFO"
    assert s.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert s.agent_max_steps == 3
    assert s.checkpoint_path.name == "checkpoints.sqlite"


def test_cors_origins_are_split_and_trimmed() -> None:
    s = _settings(cors_origins="http://localhost:5173, http://127.0.0.1:5173, ")
    assert s.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]


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
