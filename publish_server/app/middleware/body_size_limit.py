"""リクエストボディサイズの事前拒否（開発Todo_Web公開_v1.0 単位2、D-20・STRIDE分析5章
「巨大ペイロード送信によるリソース枯渇」）。

`Content-Length`ヘッダの時点で明らかに上限超過なら、JSONパース前に413で拒否する粗い防御。
上限値のちょうどの境界判定（JSON化後の正確なサイズ）は`app/services/publish_service.py`が
行う。ここでの倍数（×2）は、スナップショット本体（items/cards/questions）以外のラッパー
フィールド（`goal_name`等）分のオーバーヘッドを許容するための緩いバッファ。

既知の限界（injection-reviewerレビュー2026-11-28指摘）：`Transfer-Encoding: chunked`で
`Content-Length`ヘッダ自体を送らないクライアントに対してはこのチェックが完全にスキップされ、
巨大ボディがそのまま`_check_snapshot_size`（JSON全文のデコード後）まで到達する。この防御は
`Content-Length`を送る通常のHTTPクライアントを想定した「粗い」事前拒否であり、本番運用では
前段のリバースプロキシ（Render、付録A・`docs/INFRASTRUCTURE.md`）側のボディサイズ制限
（`client_max_body_size`相当）が真の防御層になる前提。ASGIの`receive()`をラップして受信中の
累積バイト数を数える方式への強化は、既に`_check_snapshot_size`が正確な上限を担保している
こととのコスト対効果を踏まえ、単位2では見送った。
"""

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from app.config import get_settings

_OVERHEAD_FACTOR = 2


def register_body_size_limit_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        settings = get_settings()
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                size = None
            if size is not None and size > settings.max_snapshot_bytes * _OVERHEAD_FACTOR:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": "Request body is too large",
                        }
                    },
                )
        return await call_next(request)
