"""app/api/errors.py のテスト（D-24、別実装のドメイン例外→HTTP変換）。"""

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api import auth as auth_module
from app.api.errors import _STATUS_AND_CODE
from app.main import create_app
from app.services.exceptions import DomainError


def test_every_registered_exception_is_a_domain_error_subclass():
    for exception_type, (status_code, code) in _STATUS_AND_CODE.items():
        assert issubclass(exception_type, DomainError), exception_type
        assert 400 <= status_code < 600, (exception_type, status_code)
        assert code == code.upper(), (exception_type, code)


def test_request_validation_error_returns_400_validation_error(client):
    response = client.post("/api/v1/auth/account", json={})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unexpected_exception_returns_internal_error_body(monkeypatch):
    def _boom(_db, _username, _password):
        raise RuntimeError("unexpected failure (test)")

    monkeypatch.setattr(auth_module.account_service, "create_account", _boom)

    app = create_app()
    with TestClient(
        app, base_url="https://testserver", raise_server_exceptions=False
    ) as non_raising_client:
        response = non_raising_client.post(
            "/api/v1/auth/account", json={"username": "zz_boom", "password": "whatever-password"}
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}
    }


def test_database_error_returns_internal_error_without_leaking_exception_text(monkeypatch, caplog):
    """DB関連例外はSQLAlchemyError専用ハンドラで捕捉し、ログにも例外文字列を残さない
    （secret-reviewerレビュー2026-11-28指摘、`app/api/errors.py`の`handle_database_error`）。
    """
    import logging

    def _boom(_db, _username, _password):
        raise OperationalError(
            "SELECT 1", {}, Exception("connection to server at secret-host failed: bad password")
        )

    monkeypatch.setattr(auth_module.account_service, "create_account", _boom)

    app = create_app()
    with (
        TestClient(
            app, base_url="https://testserver", raise_server_exceptions=False
        ) as non_raising_client,
        caplog.at_level(logging.ERROR, logger="app.api.errors"),
    ):
        response = non_raising_client.post(
            "/api/v1/auth/account", json={"username": "zz_dbboom", "password": "whatever-password"}
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}
    }
    messages = [r.getMessage() for r in caplog.records if r.name == "app.api.errors"]
    assert any("OperationalError" in message for message in messages)
    assert not any("secret-host" in message for message in messages)
