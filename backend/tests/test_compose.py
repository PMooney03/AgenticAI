from pathlib import Path

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def test_compose_file_declares_localhost_bound_services() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "qdrant:" in text
    assert "backend:" in text
    assert "frontend:" in text
    assert 'profiles: ["app"]' in text or "profiles: ['app']" in text
    assert "127.0.0.1:8000:8000" in text
    assert "127.0.0.1:8080:80" in text
    assert "127.0.0.1:6333:6333" in text
    assert "host.docker.internal" in text
    assert "QDRANT_URL: http://qdrant:6333" in text
    assert "DATA_DIR: /data" in text
