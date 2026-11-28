"""Alembicマイグレーションの「既存データに対する安全性」を検証するテスト向けの共通処理
（CODING_RULES.md「DBマイグレーションのテスト」、backend/tests/migration_helpers.pyと同じ方針。
別実装、D-24と同種）。

既存テーブルへの列追加・変更を伴うマイグレーションを追加する際は、本モジュールを使って
「既存データがある状態での適用」を検証するテストを必ず追加する。
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

PUBLISH_SERVER_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI_PATH = PUBLISH_SERVER_DIR / "alembic.ini"


@contextmanager
def preserve_logging_state() -> Iterator[None]:
    """`alembic`の`fileConfig()`（`disable_existing_loggers`既定True）から既存ロガーを守る
    （`conftest.py`の`_migrated_database`フィクスチャと同じ理由。複数の呼び出し元から
    使うため、tests/conftest.pyから本モジュールへ集約した）。
    """
    import logging

    root_logger = logging.getLogger()
    disabled_snapshot = {
        name: logger_obj.disabled
        for name, logger_obj in root_logger.manager.loggerDict.items()
        if isinstance(logger_obj, logging.Logger)
    }
    try:
        yield
    finally:
        for name, was_disabled in disabled_snapshot.items():
            logger_obj = root_logger.manager.loggerDict.get(name)
            if isinstance(logger_obj, logging.Logger):
                logger_obj.disabled = was_disabled


@contextmanager
def sqlite_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    """テスト用DBへ直接つなぐ（適用前の行の投入と、適用後の検証で使う）。

    正常終了時のみcommitする（`backend/tests/migration_helpers.py`と同じ設計）。
    """
    connection = sqlite3.connect(db_path)
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
