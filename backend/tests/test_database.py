"""app.database のテスト（起動直後の複数リクエスト同時実行時に`database is locked`が
発生する不具合の回帰防止、2026-10-01実機確認）。

本番相当のSQLite接続設定（busy timeout・WALモード）と、`-wal`補助ファイルの内容を
本体ファイルへ統合してから複製する`checkpoint_and_dispose`（backup_service・
app.main.upgrade_database_schemaのファイルコピー処理で共用）を検証する。
"""

import shutil
import sqlite3

from sqlalchemy import text

from app.database import _SQLITE_BUSY_TIMEOUT_SECONDS, checkpoint_and_dispose, create_db_engine


def test_create_db_engine_sets_sqlite_busy_timeout(tmp_path):
    """sqlite3既定の5秒では、AI基盤への応答待ちを挟む書き込みトランザクションと
    重なった際に`database is locked`で失敗しうるため、明示的に延長していることを確認する。"""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'x.db'}")
    try:
        with engine.connect() as connection:
            busy_timeout_ms = connection.execute(text("PRAGMA busy_timeout")).scalar()
        assert busy_timeout_ms == _SQLITE_BUSY_TIMEOUT_SECONDS * 1000
    finally:
        engine.dispose()


def test_create_db_engine_enables_wal_mode(tmp_path):
    """読み取りが書き込みをブロックしないWALモードを有効化していることを確認する
    （既定のDELETEモードでは書き込み中の他接続の読み取り・書き込みが待たされる）。"""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'x.db'}")
    try:
        with engine.connect() as connection:
            journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar()
        assert journal_mode == "wal"
    finally:
        engine.dispose()


def test_checkpoint_and_dispose_merges_wal_content_before_raw_file_copy(tmp_path):
    """WALモードでは直近のコミット内容が本体ファイルでなく`-wal`補助ファイル側にのみ
    存在しうる。`checkpoint_and_dispose`を呼ばずに本体ファイルだけを`shutil.copy2`で
    複製すると、直近の変更が複製先から失われる（バックアップ・安全退避コピーが
    不完全になる）。backup_service.create_backup等と同じ手順（engineの書き込み→
    checkpoint_and_dispose→本体ファイルのみ複製）で、複製先に全データが残ることを確認する。
    """
    db_path = tmp_path / "source.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    with engine.connect() as connection:
        connection.execute(text("CREATE TABLE marker (id INTEGER PRIMARY KEY, value TEXT)"))
        connection.execute(text("INSERT INTO marker (id, value) VALUES (1, 'checkpoint前')"))
        connection.commit()

    checkpoint_and_dispose(engine)

    # 本体ファイル1つだけを複製する（backup_service.create_backup等と同じ操作）。
    # -wal/-shm補助ファイルは複製しない（チェックポイントにより本体へ統合済みの前提）。
    destination = tmp_path / "destination.db"
    shutil.copy2(db_path, destination)

    connection = sqlite3.connect(destination)
    try:
        value = connection.execute("SELECT value FROM marker WHERE id = 1").fetchone()[0]
    finally:
        connection.close()
    assert value == "checkpoint前"
