"""未分類の例外に対する応答形式のテスト（app/api/errors.py の Exception ハンドラ）。

DomainErrorでもRequestValidationErrorでもない想定外の例外が、本アプリの
{"error": {"code", "message", "details"}} 形式（データ構造編6.1）でINTERNAL_ERRORとして
返ることを検証する。これが無いと、フロントのエラー解析（error.codeを前提とする）が
破綻し、利用者に何も表示されない事態になりうる（2026-09-19、非エンジニア向けエラー
表示改善で発見）。
"""

from app.ai import auth as ai_auth


def test_unexpected_exception_returns_internal_error_body(client, monkeypatch):
    def _boom(_session):
        raise RuntimeError("想定外の内部エラー（テスト用）")

    monkeypatch.setattr(ai_auth, "get_status", _boom)

    response = client.get("/api/v1/ai/status")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "予期しないエラーが発生しました",
            "details": [],
        }
    }
