"""publish_server アプリケーション起動（開発Todo_Web公開_v1.0 単位1）。

backendの`app/main.py`とは別プロセス・別デプロイ単位（D-12・D-23）。ベースパスは
データ構造編6.1に揃えて`/api/v1`を使うが、ルーター自体は独立実装である（D-24）。
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.config import get_settings
from app.constants.security import CSRF_HEADER_NAME
from app.middleware.security_headers import register_security_headers_middleware

API_V1_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(title="Michinari Publish Server")

    register_security_headers_middleware(app)

    allowed_origins = [
        origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()
    ]
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type", CSRF_HEADER_NAME],
        )

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(auth_router, prefix=API_V1_PREFIX)

    return app


app = create_app()
