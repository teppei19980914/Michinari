"""リクエストボディサイズ事前拒否ミドルウェアのテスト（開発Todo_Web公開_v1.0 単位2、
D-20・STRIDE分析5章「巨大ペイロード送信によるリソース枯渇」）。
"""

from tests.publish_helpers import bearer_header, create_and_login, gantt_payload, issue_api_token


def test_oversized_content_length_is_rejected_before_parsing(client, monkeypatch):
    csrf = create_and_login(client, "alice")
    token = issue_api_token(client, csrf)
    # 上限をごく小さくすることで、通常サイズのリクエストでも必ず超過させる
    # （JSON化後サイズの正確な境界判定は`app/services/publish_service.py`側のテストで検証する）。
    monkeypatch.setenv("PUBLISH_MAX_SNAPSHOT_BYTES", "5")

    response = client.put(
        "/api/v1/publish/gantt/1", json=gantt_payload(), headers=bearer_header(token)
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_request_without_content_length_passes_through(client):
    """GETリクエスト（ボディ無し）はContent-Lengthが無いため、常にミドルウェアを通過する。"""
    response = client.get("/health")

    assert response.status_code == 200


def test_non_numeric_content_length_header_passes_through_to_normal_validation(client, monkeypatch):
    """`Content-Length`が数値でない場合は粗い防御をスキップし、後続の通常の検証に委ねる。"""
    csrf = create_and_login(client, "bob")
    token = issue_api_token(client, csrf)

    response = client.put(
        "/api/v1/publish/gantt/1",
        json=gantt_payload(),
        headers={**bearer_header(token), "content-length": "not-a-number"},
    )

    assert response.status_code == 204
