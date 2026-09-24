"""client_logs API のテスト（Phase40 診断ログ出力・トレース強化）。

Reactの`ErrorBoundary`が構造的に捕捉できないイベントハンドラ内・非同期処理内の例外や、
描画中の例外を、バックエンドの診断ログへ一本化して残すためのエンドポイント。
"""

import logging

_ENDPOINT = "/api/v1/client-logs"


def test_records_a_client_error_in_the_log(client, caplog):
    with caplog.at_level(logging.WARNING, logger="app.client"):
        response = client.post(
            _ENDPOINT,
            json={
                "level": "error",
                "message": "Cannot read properties of undefined",
                "stack": "TypeError: ...\n  at Component (App.tsx:10)",
                "path": "/dashboard",
            },
        )

    assert response.status_code == 204
    messages = [r.getMessage() for r in caplog.records if r.name == "app.client"]
    assert any("Cannot read properties of undefined" in m for m in messages)
    assert any("TypeError" in m for m in messages)


def test_accepts_a_request_without_stack_or_component_stack(client):
    response = client.post(
        _ENDPOINT,
        json={"level": "error", "message": "boom", "path": "/"},
    )

    assert response.status_code == 204


def test_rejects_a_message_longer_than_the_limit(client):
    response = client.post(
        _ENDPOINT,
        json={"level": "error", "message": "a" * 4001, "path": "/"},
    )

    assert response.status_code == 400


def test_sanitizes_embedded_newlines_in_the_single_line_message(client, caplog):
    """messageへの改行混入で偽のログ行を作れないこと（脅威モデルT対策）。"""
    with caplog.at_level(logging.WARNING, logger="app.client"):
        response = client.post(
            _ENDPOINT,
            json={
                "level": "error",
                "message": "line1\n2026-01-01 00:00:00,000 ERROR    [-] app: 偽装行",
                "path": "/",
            },
        )

    assert response.status_code == 204
    messages = [r.getMessage() for r in caplog.records if r.name == "app.client"]
    assert any(r"line1\n2026-01-01" in m for m in messages)
    assert not any("\n2026-01-01" in m for m in messages)
