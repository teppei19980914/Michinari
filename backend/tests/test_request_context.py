"""request_context ミドルウェアのテスト（Phase40 診断ログ出力・トレース強化）。

`client`フィクスチャ（conftest.py）経由で実際にアプリへリクエストを送り、
相関IDがレスポンスヘッダに乗ること・同じIDでログ行が出力されることを確かめる。
"""

import logging

from app.middleware.request_context import REQUEST_ID_HEADER, request_id_ctx


def test_response_has_a_request_id_header(client):
    response = client.get("/health")

    assert response.headers[REQUEST_ID_HEADER]


def test_request_id_differs_between_requests(client):
    first = client.get("/health").headers[REQUEST_ID_HEADER]
    second = client.get("/health").headers[REQUEST_ID_HEADER]

    assert first != second


def test_access_log_line_carries_the_same_request_id(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        response = client.get("/health")

    request_id = response.headers[REQUEST_ID_HEADER]
    access_records = [r for r in caplog.records if r.name == "app.access"]
    assert access_records, "app.access ロガーへの出力が無い"
    assert access_records[-1].request_id == request_id


def test_request_id_ctx_resets_to_default_outside_a_request(client):
    client.get("/health")

    assert request_id_ctx.get() == "-"
