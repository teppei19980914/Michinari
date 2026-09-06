"""SQLAlchemy セッション管理。

SQLite は外部キー制約が既定で無効なため、接続ごとに
`PRAGMA foreign_keys = ON` を実行する（設計書 データ構造編 2章）。
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.base import Base


def create_db_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)

    # 技術選定書のSQLite以外の分岐は将来のPostgreSQL移行に備えた保険であり、
    # 現行運用（SQLite固定）ではテスト対象から除外する。
    if url.startswith("sqlite"):  # pragma: no branch

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()

    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables(bind: Engine | None = None) -> None:
    """開発・テスト用途。本番相当の構築は Alembic マイグレーションで行う。"""
    Base.metadata.create_all(bind=bind or engine)
