"""app/main.py create_app() のテスト（CORS設定の分岐、D-18）。"""

from fastapi.testclient import TestClient

from app.main import create_app


def test_create_app_without_cors_origins_omits_cors_headers(monkeypatch):
    monkeypatch.setenv("PUBLISH_CORS_ALLOWED_ORIGINS", "")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as test_client:
        response = test_client.get("/health", headers={"Origin": "https://viewer.example.com"})

    assert "access-control-allow-origin" not in response.headers


def test_create_app_with_cors_origins_allows_configured_origin(monkeypatch):
    monkeypatch.setenv("PUBLISH_CORS_ALLOWED_ORIGINS", "https://viewer.example.com")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as test_client:
        response = test_client.get("/health", headers={"Origin": "https://viewer.example.com"})

    assert response.headers.get("access-control-allow-origin") == "https://viewer.example.com"


def test_create_app_with_cors_origins_rejects_other_origin(monkeypatch):
    monkeypatch.setenv("PUBLISH_CORS_ALLOWED_ORIGINS", "https://viewer.example.com")
    app = create_app()

    with TestClient(app, base_url="https://testserver") as test_client:
        response = test_client.get("/health", headers={"Origin": "https://evil.example.com"})

    assert "access-control-allow-origin" not in response.headers
