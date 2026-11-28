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
