"""リクエストボディサイズの事前拒否（開発Todo_Web公開_v1.0 単位2、D-20・STRIDE分析5章
「巨大ペイロード送信によるリソース枯渇」）。

`Content-Length`ヘッダの時点で明らかに上限超過なら、JSONパース前に413で拒否する粗い防御。
上限値のちょうどの境界判定（JSON化後の正確なサイズ）は`app/services/publish_service.py`が
行う。ここでの倍数（×2）は、スナップショット本体（items/cards/questions）以外のラッパー
フィールド（`goal_name`等）分のオーバーヘッドを許容するための緩いバッファ。
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
