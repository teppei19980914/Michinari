"""GET /health のテスト（付録A デプロイ手順6、認証不要）。"""

from sqlalchemy.exc import OperationalError

from app.api import health as health_module


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_returns_503_when_database_unreachable(client, monkeypatch):
    def _raise_operational_error(_self, *_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr("sqlalchemy.orm.Session.execute", _raise_operational_error)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unreachable"}


def test_health_route_requires_no_auth():
    assert "health" in [route.name for route in health_module.router.routes]
