from fastapi.testclient import TestClient


def test_preflight_allows_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type,x-request-id",
        },
    )
    assert response.status_code in {200, 204}
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    allow_methods = response.headers.get("access-control-allow-methods", "").upper()
    assert "GET" in allow_methods


def test_preflight_rejects_unknown_origin(client: TestClient) -> None:
    response = client.options(
        "/chat",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_actual_request_echoes_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    exposed = response.headers.get("access-control-expose-headers", "").lower()
    assert "x-request-id" in exposed
