import os

from fastapi.testclient import TestClient

from app.main import create_app
from app.middleware.body_size_limit import compute_max_body_size
from tests.publish_helpers import bearer_header, create_and_login, issue_api_token


def test_probe_413_headers(db_session, monkeypatch):
    monkeypatch.setenv("PUBLISH_CORS_ALLOWED_ORIGINS", "https://example-viewer.test")
    app = create_app()
    with TestClient(app, base_url="https://testserver") as client:
        csrf = create_and_login(client, "probeuser")
        token = issue_api_token(client, csrf)
        oversized_body = b"a" * (compute_max_body_size() + 1)
        resp = client.put(
            "/api/v1/publish/gantt/1",
            content=oversized_body,
            headers={
                **bearer_header(token),
                "content-type": "application/json",
                "Origin": "https://example-viewer.test",
            },
        )
        print("STATUS", resp.status_code)
        print("CONTENT-TYPE", resp.headers.get("content-type"))
        print("BODY", repr(resp.text[:300]))
        print("ACAO", resp.headers.get("access-control-allow-origin"))
        print("ACAC", resp.headers.get("access-control-allow-credentials"))
        print("XCTO", resp.headers.get("x-content-type-options"))
        print("CSP", resp.headers.get("content-security-policy"))
        print("XFO", resp.headers.get("x-frame-options"))
        print("ALL", dict(resp.headers))
