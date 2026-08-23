"""アプリケーション起動（設計書 データ構造編 8章）。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.api.errors import register_exception_handlers
from app.api.goals import router as goals_router
from app.api.materials import router as materials_router
from app.api.resources import router as resources_router
from app.config import get_settings
from app.constants.app_setting_keys import SERVER_PORT
from app.database import SessionLocal, create_all_tables
from app.init.seed_data import run_all
from app.models.setting import AppSetting

#: データ構造編6.1「ベースパス /api/v1」。
API_V1_PREFIX = "/api/v1"


def bootstrap_database() -> None:
    """テーブル作成（本番相当は Alembic）と初期データ投入をまとめて行う。"""
    create_all_tables()
    session = SessionLocal()
    try:
        run_all(session)
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    bootstrap_database()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ミチナリ API", lifespan=lifespan)
    register_exception_handlers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(goals_router, prefix=API_V1_PREFIX)
    app.include_router(materials_router, prefix=API_V1_PREFIX)
    app.include_router(resources_router, prefix=API_V1_PREFIX)

    return app


app = create_app()


def port_from_app_setting(session: Session) -> int:
    """server.port（app_setting）を返す。行が存在しない場合のみ設定ファイルの
    フォールバック値を使う（DB未構築直後などのブートストラップ用）。"""
    setting = session.query(AppSetting).filter_by(key=SERVER_PORT).first()
    return int(setting.value) if setting else get_settings().fallback_server_port


def resolve_startup_port() -> int:
    bootstrap_database()
    session = SessionLocal()
    try:
        return port_from_app_setting(session)
    finally:
        session.close()


if __name__ == "__main__":  # pragma: no cover (実サーバ起動のためユニットテスト対象外)
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=resolve_startup_port())
