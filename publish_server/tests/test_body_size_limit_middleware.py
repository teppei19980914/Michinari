"""リクエストボディサイズ事前拒否のテスト（開発Todo_Web公開_v1.0 単位2、D-20・
STRIDE分析5章「巨大ペイロード送信によるリソース枯渇」）。

FastAPI/Starlette一次サポートの`max_body_size`（`app/middleware/body_size_limit.py`・
`app/main.py`）は実際に受信したバイト数で判定するため、`Content-Length`ヘッダに依存しない
（`Transfer-Encoding: chunked`等でヘッダ自体が無くても迂回できない設計）。

閾値は`create_app()`実行時に1回だけ固定される（Starletteの`max_body_size`の仕様上、CORS
許可オリジンと同じ扱い）ため、他のテストのように`monkeypatch.setenv`を実行後に変えることは
できない。既定の閾値（`PUBLISH_MAX_SNAPSHOT_BYTES`既定2MB×2倍＝4MB）に対して、実際に
それを超える生バイト列を送ることで検証する（JSONとして妥当である必要はない。pydanticの
検証より前にASGI層で拒否されるため）。
"""

from app.config import get_settings
from app.middleware.body_size_limit import compute_max_body_size
from tests.publish_helpers import bearer_header, create_and_login, gantt_payload, issue_api_token


def test_compute_max_body_size_applies_overhead_factor():
    """`OVERHEAD_FACTOR`（×2倍）自体の効果を検証する（test-coverage-reviewerレビュー
    2026-11-28指摘：HTTP経由のテストだけでは`compute_max_body_size()`がテストデータ構築に
    使われるだけでトートロジーになり、倍率の値そのものの変更を検知できない）。期待値は
    定数名を参照せず数値`2`を直接書く（定数の書き換えミスを検知できるようにするため）。
    """
    settings = get_settings()

    assert compute_max_body_size() == settings.max_snapshot_bytes * 2


def test_oversized_raw_body_is_rejected_with_413_regardless_of_json_validity(client):
    csrf = create_and_login(client, "alice")
    token = issue_api_token(client, csrf)
    oversized_body = b"a" * (compute_max_body_size() + 1)

    response = client.put(
        "/api/v1/publish/gantt/1",
        content=oversized_body,
        headers={**bearer_header(token), "content-type": "application/json"},
    )

    assert response.status_code == 413


def test_body_exactly_at_threshold_is_not_rejected_with_413(client):
    """境界値（ちょうど閾値）は拒否されないことを確認する（test-coverage-reviewerレビュー
    2026-11-28指摘：Starletteの判定は厳密な`>`〈`.venv/Lib/site-packages/starlette/
    middleware/body_limit.py`で確認済み〉のため、off-by-oneでの回帰〈`>=`化等〉を検知する）。
    JSONとして妥当である必要はない（ASGI層での拒否はpydantic検証より前に行われるため）。
    """
    csrf = create_and_login(client, "alice2")
    token = issue_api_token(client, csrf)
    body_at_threshold = b"a" * compute_max_body_size()

    response = client.put(
        "/api/v1/publish/gantt/1",
        content=body_at_threshold,
        headers={**bearer_header(token), "content-type": "application/json"},
    )

    assert response.status_code != 413


def test_normal_sized_request_passes_through(client):
    csrf = create_and_login(client, "bob")
    token = issue_api_token(client, csrf)

    response = client.put(
        "/api/v1/publish/gantt/1", json=gantt_payload(), headers=bearer_header(token)
    )

    assert response.status_code == 204


def test_request_without_body_passes_through(client):
    """GETリクエスト（ボディ無し）は受信バイト数が常に0のため、常に閾値未満で通過する。"""
    response = client.get("/health")

    assert response.status_code == 200
