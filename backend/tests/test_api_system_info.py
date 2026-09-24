"""システム情報APIのテスト（仕様書6.14 SC-15）。"""

from app.services import system_log_export_service


def test_get_system_info_returns_app_version_and_libraries(client):
    response = client.get("/api/v1/system-info")

    assert response.status_code == 200
    body = response.json()
    assert body["app_version"]
    assert body["python_version"]
    assert body["built_at"] is None
    assert any(lib["name"] == "fastapi" for lib in body["backend_libraries"])
    assert any(lib["name"] == "react" for lib in body["frontend_libraries"])


class TestExportLogs:
    """ログエクスポートAPIのテスト（Phase40 診断ログ出力・トレース強化）。

    実ログファイル（`data/logs`）には触れず、サービス層をスタブに差し替えて
    レスポンスの組み立て（Content-Disposition・本文）のみを検証する。フィルタの
    正しさ自体は test_system_log_export_service.py が担う。
    """

    def test_returns_the_log_content_as_a_downloadable_text_file(self, client, monkeypatch):
        monkeypatch.setattr(
            system_log_export_service, "export_logs", lambda *_args, **_kwargs: "ログの中身"
        )

        response = client.get(
            "/api/v1/system-info/logs/export?date_from=2026-09-01&date_to=2026-09-23"
        )

        assert response.status_code == 200
        assert response.text == "ログの中身"
        assert response.headers["content-type"].startswith("text/plain")
        assert "michinari-logs_2026-09-01_2026-09-23.log" in response.headers["content-disposition"]

    def test_rejects_an_invalid_date_range(self, client):
        response = client.get(
            "/api/v1/system-info/logs/export?date_from=2026-09-23&date_to=2026-09-01"
        )

        assert response.status_code == 400
