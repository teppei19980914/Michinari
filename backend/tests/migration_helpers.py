"""Alembicマイグレーションの「既存データに対する安全性」を検証するテスト向けの共通処理
（CODING_RULES.md「既存テーブルを変更するマイグレーションのテスト」参照）。

2026-08-29、exam_subject.passing_score_type列追加マイグレーションが、空DBのみを対象と
する既存のテスト（conftest.pyのセッション単位フィクスチャ）では検出できない不具合
（SQLiteのbatch mode—env.pyのrender_as_batch=True—でのテーブル再作成時にserver_default
が失われ、既存行のコピーがNOT NULL制約違反になる）を含んだまま配布され、利用者の環境で
初めて発覚した。以後、既存テーブルへの列追加・変更を伴うマイグレーションを追加する際は、
本モジュールを使って「既存データがある状態での適用」を検証するテストを必ず追加する。
"""

import sqlite3
from pathlib import Path

from alembic.config import Config

from alembic import command

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ALEMBIC_INI_PATH = _BACKEND_DIR / "alembic.ini"


def build_alembic_config() -> Config:
    """実プロジェクトのalembic.iniを指すConfigを返す（script_locationの解決に使う）。"""
    return Config(str(_ALEMBIC_INI_PATH))


def upgrade_to(revision: str) -> None:
    """現在の`MICHINARI_DATABASE_URL`が指すDBを指定リビジョンまで適用する。

    呼び出し側が事前に`monkeypatch.setenv("MICHINARI_DATABASE_URL", "sqlite:///...")`で
    テスト用DBファイルへ切り替えておくこと（alembic/env.pyがapp.config.get_settings()
    経由で接続先を解決するため、切り替えを忘れると実行中の共有テストDBを書き換えてしまう）。
    """
    command.upgrade(build_alembic_config(), revision)


def drop_alembic_version_table(db_path: Path) -> None:
    """`alembic_version`テーブルを削除し、『create_all_tables()のみで構築され、一度も
    Alembicで管理されていない既存DB』を再現する（app.main._PRE_ALEMBIC_BASELINE_REVISION
    経由のstamp分岐を検証する際に使う）。
    """
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("DROP TABLE IF EXISTS alembic_version")
        connection.commit()
    finally:
        connection.close()
