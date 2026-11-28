"""SQLAlchemy セッション管理（publish_server）。

本番はPostgreSQL（D-13・D-23、Supabase）。開発・テストではSQLiteの既定値で動作する
（app/config.py参照）。SQLiteはテスト実行時のみ使うため、backend/app/database.pyと同じく
外部キー制約を有効化する（D-23のON DELETE CASCADE設計をテストでも検証できるようにする）。
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.base import Base


def create_db_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)

    if url.startswith("sqlite"):  # pragma: no branch

        @event.listens_for(engine, "connect")
        def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
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


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """コミット/ロールバックまでを呼び出し側で意識させたくない短い処理向け（起動時シード等）。"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_all_tables(bind: Engine | None = None) -> None:
    """開発・テスト用途。本番相当の構築はAlembicマイグレーションで行う。"""
    Base.metadata.create_all(bind=bind or engine)
