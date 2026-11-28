"""セキュリティヘッダ・CSPミドルウェア（D-18）。

publish_serverは単位1時点ではJSON APIのみを返す（HTMLは配信しない。公開ビューアは単位3で
別途実装）。そのため`default-src 'none'`を既定とする、ブラウザに解釈させる必要のある
コンテンツが無い前提の厳格なCSPにしている。単位3でビューア用の静的配信を追加する際は、
その配信元のCSPを別途見直す必要がある（本モジュールはAPIレスポンスに対してのみ適用）。
"""

from fastapi import FastAPI, Request
from starlette.responses import Response

_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    # TLS終端は前段（Render等、付録A参照）が行う前提だが、HTTPS経由で届いたレスポンスに対しては
    # ブラウザ側でHSTSを有効化してよい（HTTP応答時はブラウザがこのヘッダを無視するため無害）。
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}


def register_security_headers_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        for name, value in _HEADERS.items():
            response.headers[name] = value
        return response
