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

#: SQLiteの書き込みロック待ち上限秒数（sqlite3既定の5秒では、AI基盤への応答待ちを挟む
#: 書き込みトランザクション（`app/ai/conversation.py`のensure_conversation等）と重なると
#: `database is locked`で失敗しうる（2026-10-01実機確認）。DB起動前に必要な値のため
#: app_settingには置けない（CLAUDE.mdゼロハードコーディングの対象外。起動間隔の
#: FALLBACK_CHECK_INTERVAL_SECONDS、app/desktop/scheduler.pyと同種の例外）。
_SQLITE_BUSY_TIMEOUT_SECONDS = 30


def create_db_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    connect_args = (
        {"check_same_thread": False, "timeout": _SQLITE_BUSY_TIMEOUT_SECONDS}
        if url.startswith("sqlite")
        else {}
    )
    engine = create_engine(url, connect_args=connect_args)

    # 技術選定書のSQLite以外の分岐は将来のPostgreSQL移行に備えた保険であり、
    # 現行運用（SQLite固定）ではテスト対象から除外する。
    if url.startswith("sqlite"):  # pragma: no branch

        @event.listens_for(engine, "connect")
        def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            # WALモード: 読み取りが書き込みをブロックしない（既定のDELETEモードでは
            # 書き込みトランザクション中の他接続の読み取り・書き込みが待たされる）。
            cursor.execute("PRAGMA journal_mode = WAL")
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


def checkpoint_and_dispose(target_engine: Engine) -> None:
    """DBファイルを`shutil.copy2`等で直接コピーする前に呼ぶ（`backup_service`・
    `app.main.upgrade_database_schema`のバックアップ/安全退避コピー処理で共用。
    CLAUDE.md DRYの原則）。

    WALモードではコミット済みの内容が本体ファイルでなく`-wal`補助ファイル側にのみ
    存在しうるため、本体ファイルの単純コピーだけでは直近の変更が失われる。
    `wal_checkpoint(TRUNCATE)`で`-wal`の内容を本体へ統合し`-wal`を空にしてから
    （コピー対象が本体ファイル1つで完結する状態にしてから）接続を解放する。
    """
    # create_db_engineの分岐と同じ理由（将来のPostgreSQL移行に備えた保険）でテスト対象から除外。
    if target_engine.dialect.name == "sqlite":  # pragma: no branch
        with target_engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    target_engine.dispose()
