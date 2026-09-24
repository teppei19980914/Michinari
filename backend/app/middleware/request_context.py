"""リクエスト相関ID（Phase40 診断ログ出力・トレース強化）。

業務エラー・アクセスログ・フロントのエラー表示を1つのIDで紐付けるための基盤。
`ContextVar`はリクエストごとに新しいasyncioタスクへ乗るため、同時に複数リクエストが
処理されていても値が混線しない（Starletteの各リクエストはタスクとして処理される）。

相関IDをログレコードへ差し込むのに`logging.Filter`ではなく`setLogRecordFactory`を使う。
`Logger.callHandlers`はハンドラ単位の`filter`しか呼ばないため、`logging_setup.configure`で
組み立てたハンドラに付けたFilterは、それ以外のハンドラ（テストの`caplog`が使う専用
ハンドラ等）には効かない。`setLogRecordFactory`はレコード生成そのものに介入するため、
`app/api/errors.py`の各例外ハンドラや`app/services/*`の奥深くのログ呼び出しまで
逐一IDを引き回さずに済み、かつどのハンドラで受けても`record.request_id`が必ず載る。
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


def _install_request_id_log_record_factory() -> None:
    """全ての`LogRecord`に`request_id`属性を持たせる（本モジュールのimport時に1回だけ実行）。

    プロセス全体で単一のレコードファクトリを使うPythonの`logging`モジュールの仕組み上、
    ここでの差し替えは以後生成される全レコード（あらゆるロガー・あらゆるハンドラ）に効く。
    二重install（テストでの再importや複数回の`create_app`呼び出し）で多重ラップしないよう、
    既に差し込み済みかを属性で確認する。
    """
    current_factory = logging.getLogRecordFactory()
    if getattr(current_factory, "_michinari_request_id_installed", False):
        return

    def factory(*args: object, **kwargs: object) -> logging.LogRecord:
        record = current_factory(*args, **kwargs)
        record.request_id = request_id_ctx.get()
        return record

    factory._michinari_request_id_installed = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(factory)


_install_request_id_log_record_factory()


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
