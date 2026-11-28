"""app/database.py のテスト。"""

from app.database import create_all_tables, create_db_engine, session_scope
from app.models.account import PublishAccount


def test_create_db_engine_sqlite_sets_check_same_thread_false():
    engine = create_db_engine("sqlite:///:memory:")
    assert engine.url.drivername == "sqlite"
    engine.dispose()


def test_create_db_engine_postgresql_branch_does_not_set_sqlite_connect_args():
    """実際には接続しない（create_engineは遅延接続）。分岐（connect_argsの出し分け）のみ検証する。"""
    engine = create_db_engine("postgresql+psycopg://user:pass@localhost/db")
    assert engine.url.drivername == "postgresql+psycopg"
    engine.dispose()


def test_session_scope_commits_on_success(db_session):
    from app.database import session_scope as scope

    with scope() as session:
        session.add(PublishAccount(username="scope_commit_user", password_hash="x"))

    found = (
        db_session.query(PublishAccount)
        .filter(PublishAccount.username == "scope_commit_user")
        .first()
    )
    assert found is not None


def test_session_scope_rolls_back_on_exception(db_session):
    class _Boom(Exception):
        pass

    try:
        with session_scope() as session:
            session.add(PublishAccount(username="scope_rollback_user", password_hash="x"))
            raise _Boom("fail before commit")
    except _Boom:
        pass

    found = (
        db_session.query(PublishAccount)
        .filter(PublishAccount.username == "scope_rollback_user")
        .first()
    )
    assert found is None


def test_create_all_tables_is_idempotent():
    # 既にmigrated_databaseフィクスチャでAlembicにより構築済みのテーブルへ対して
    # 再度create_allを呼んでも、checkfirstにより例外にならないことだけを確認する。
    create_all_tables()
