"""リクエスト相関ID（Phase40 診断ログ出力・トレース強化）。

業務エラー・アクセスログ・フロントのエラー表示を1つのIDで紐付けるための基盤。
`ContextVar`はリクエストごとに新しいasyncioタスクへ乗るため、同時に複数リクエストが
処理されていても値が混線しない（Starletteの各リクエストはタスクとして処理される）。

`logging.Filter`でログレコードへ自動的に相関IDを差し込む方式を取るのは、
`app/api/errors.py`の各例外ハンドラや`app/services/*`の奥深くのログ呼び出しにまで
逐一IDを引き回さずに済ませるため（呼び出し側は今まで通りのログ呼び出しのままでよい）。
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request

#: 相関IDの既定値。リクエスト処理の外（起動処理・常駐スレッド等）で出力されるログ行は
#: この値のまま残る。
_NO_REQUEST_ID = "-"

request_id_ctx: ContextVar[str] = ContextVar("request_id", default=_NO_REQUEST_ID)

#: アクセスログ専用のロガー名（`app.access`）。業務ロジックのロガーと区別できるようにする。
_access_logger = logging.getLogger("app.access")

#: レスポンスへ付与するヘッダ名。フロントの`api/client.ts`がここから相関IDを読み取り、
#: エラー表示に「エラーID」として載せる。
REQUEST_ID_HEADER = "X-Request-Id"


class RequestIdLogFilter(logging.Filter):
    """ログレコードへ現在の相関ID（`record.request_id`）を差し込む。

    `logging_setup.LOG_FORMAT`の`%(request_id)s`に対応する。リクエスト処理外のログでは
    `request_id_ctx`の既定値（`-`）がそのまま入る。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def register_request_context_middleware(app: FastAPI) -> None:
    """`main.py`の`create_app`から呼び出す（`register_exception_handlers`と対になる登録関数）。"""

    @app.middleware("http")
    async def add_request_context(request: Request, call_next):
        request_id = uuid.uuid4().hex[:12]
        token = request_id_ctx.set(request_id)
        start = time.monotonic()
        try:
            response = await call_next(request)
            duration_ms = (time.monotonic() - start) * 1000
            response.headers[REQUEST_ID_HEADER] = request_id
            _access_logger.info(
                "%s %s -> %s (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        finally:
            request_id_ctx.reset(token)
