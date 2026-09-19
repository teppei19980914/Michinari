"""未分類の例外に対する応答形式のテスト（app/api/errors.py の Exception ハンドラ）。

DomainErrorでもRequestValidationErrorでもない想定外の例外が、本アプリの
{"error": {"code", "message", "details"}} 形式（データ構造編6.1）でINTERNAL_ERRORとして
返ることを検証する。これが無いと、フロントのエラー解析（error.codeを前提とする）が
破綻し、利用者に何も表示されない事態になりうる（2026-09-19、非エンジニア向けエラー
表示改善で発見）。

Starlette の ServerErrorMiddleware は、Exception用ハンドラで応答を組み立てて送信した後も
「サーバ側のログ・テストクライアントでの検知のため」常に例外を再送出する仕様（実サーバ
では実害なく、送信済みの応答はそのままクライアントへ届く）。既定の `client` フィクスチャの
TestClientは`raise_server_exceptions=True`のためこの再送出をテスト側の例外として拾って
しまうので、本テストのみ`raise_server_exceptions=False`のTestClientを使う。
"""

from fastapi.testclient import TestClient

from app.ai import auth as ai_auth
from app.main import app


def test_unexpected_exception_returns_internal_error_body(client, monkeypatch):
    def _boom(_session):
        raise RuntimeError("想定外の内部エラー（テスト用）")

    monkeypatch.setattr(ai_auth, "get_status", _boom)

    with TestClient(app, raise_server_exceptions=False) as non_raising_client:
        response = non_raising_client.get("/api/v1/ai/status")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "予期しないエラーが発生しました",
            "details": [],
        }
    }
