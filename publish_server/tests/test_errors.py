"""app/api/errors.py のテスト（D-24、別実装のドメイン例外→HTTP変換）。"""

from fastapi.testclient import TestClient

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
