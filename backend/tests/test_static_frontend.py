"""フロントエンドの静的配信（配布パッケージ対応）のテスト。

`npm run build` の出力（frontend/dist）を同一プロセスで配信できることと、
API/health ルートが静的配信より優先されること、React Router のクライアント側
ルーティングに対応するため未一致パスが index.html へフォールバックすることを検証する。
"""

import sys

from fastapi.testclient import TestClient

from app import main as app_main
from app.config import REPO_ROOT

# --- resolve_frontend_dist_dir ---


def test_resolve_frontend_dist_dir_uses_repo_frontend_dist_when_not_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    result = app_main.resolve_frontend_dist_dir()

    assert result == REPO_ROOT / "frontend" / "dist"


def test_resolve_frontend_dist_dir_uses_meipass_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    result = app_main.resolve_frontend_dist_dir()

    assert result == tmp_path / "frontend_dist"


def _make_app_with_dist(monkeypatch, dist_dir, *, index_body="<html>michinari</html>"):
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text(index_body, encoding="utf-8")
    monkeypatch.setattr(app_main, "resolve_frontend_dist_dir", lambda: dist_dir)
    return app_main.create_app()


def test_serves_index_html_at_root_when_dist_exists(tmp_path, monkeypatch):
    app = _make_app_with_dist(monkeypatch, tmp_path / "dist")

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "michinari" in response.text


def test_falls_back_to_index_html_for_client_side_routes(tmp_path, monkeypatch):
    """React Routerのクライアント側ルート（例: /goals/123）は実ファイルが存在しない
    ため、index.htmlへフォールバックしてフロント側のルーティングに委ねる。"""
    app = _make_app_with_dist(monkeypatch, tmp_path / "dist")

    with TestClient(app) as client:
        response = client.get("/goals/123")

    assert response.status_code == 200
    assert "michinari" in response.text


def test_health_endpoint_takes_priority_over_static_mount(tmp_path, monkeypatch):
    app = _make_app_with_dist(monkeypatch, tmp_path / "dist")

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.json() == {"status": "ok"}


def test_api_routes_take_priority_over_static_mount(tmp_path, monkeypatch):
    app = _make_app_with_dist(monkeypatch, tmp_path / "dist")

    with TestClient(app) as client:
        response = client.get("/api/v1/records/today")

    assert response.status_code == 200
    assert "logical_date" in response.json()


def test_reraises_non_404_errors_without_falling_back_to_index_html(tmp_path, monkeypatch):
    """404以外（例: GET/HEAD以外のメソッドによる405）はindex.htmlへフォールバックせず、
    そのままエラーを返す（_SpaStaticFiles.get_responseの再送出分岐）。"""
    app = _make_app_with_dist(monkeypatch, tmp_path / "dist")

    with TestClient(app) as client:
        response = client.post("/some-static-path")

    assert response.status_code == 405


def test_does_not_mount_static_when_dist_dir_absent(tmp_path, monkeypatch):
    """フロントエンド未ビルドの開発環境では静的配信をマウントせず、これまで通り
    Vite開発サーバー経由のプロキシ利用を想定する（既存の開発フローへの影響なし）。"""
    monkeypatch.setattr(app_main, "resolve_frontend_dist_dir", lambda: tmp_path / "missing")

    app = app_main.create_app()

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 404
