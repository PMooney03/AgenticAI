def test_application_factory_imports_without_cycle() -> None:
    from app.main import create_app

    app = create_app()
    paths = app.openapi()["paths"]
    assert "/chat" in paths
    assert "/agent/tools" in paths
    assert "/health" in paths
    assert "/metrics" in paths
    assert "/eval/run" in paths
    assert "/eval/latest" in paths
