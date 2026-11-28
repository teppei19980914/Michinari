"""`alembic upgrade head` でスキーマが構築されることの明示的な検証（単位1 完了条件）。

conftest.pyの`_migrated_database`（autouse）が既に実行しているが、ここでは結果
（テーブル・インデックスの存在）自体を明示的に固定する。
"""

from sqlalchemy import inspect

from app.database import engine


def test_all_unit1_tables_exist():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert {"publish_account", "publish_api_token", "publish_session", "share_link"} <= table_names


def test_publish_account_username_is_unique_indexed():
    inspector = inspect(engine)
    indexes = inspector.get_indexes("publish_account")
    username_indexes = [idx for idx in indexes if idx["column_names"] == ["username"]]

    assert any(idx["unique"] for idx in username_indexes)


def test_foreign_keys_cascade_on_delete():
    inspector = inspect(engine)
    for table_name in ("publish_api_token", "publish_session", "share_link"):
        fks = inspector.get_foreign_keys(table_name)
        assert any(fk["options"].get("ondelete") == "CASCADE" for fk in fks), table_name


def test_all_unit2_tables_exist():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert {
        "published_gantt_snapshot",
        "published_vocab_deck",
        "published_quiz_question",
        "quiz_answer_record",
    } <= table_names


def test_unit2_foreign_keys_cascade_on_delete():
    inspector = inspect(engine)
    for table_name in (
        "published_gantt_snapshot",
        "published_vocab_deck",
        "published_quiz_question",
    ):
        fks = inspector.get_foreign_keys(table_name)
        assert any(fk["options"].get("ondelete") == "CASCADE" for fk in fks), table_name


def test_quiz_answer_record_question_id_foreign_key_sets_null_on_delete():
    inspector = inspect(engine)
    fks = inspector.get_foreign_keys("quiz_answer_record")
    question_fk = next(fk for fk in fks if fk["referred_table"] == "published_quiz_question")
    assert question_fk["options"].get("ondelete") == "SET NULL"


def test_quiz_answer_record_client_answer_uuid_is_unique_indexed():
    inspector = inspect(engine)
    indexes = inspector.get_indexes("quiz_answer_record")
    uuid_indexes = [idx for idx in indexes if idx["column_names"] == ["client_answer_uuid"]]
    assert any(idx["unique"] for idx in uuid_indexes)
