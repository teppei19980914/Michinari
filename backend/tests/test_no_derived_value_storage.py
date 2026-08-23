"""完了条件: 日次ノルマ、残量、現在周回のいずれもデータベースに保存されていないこと
（設計書 データ構造編 3.1 派生値を保存しない）。
"""

from sqlalchemy import inspect

from app.database import engine

FORBIDDEN_COLUMN_NAMES = {
    "daily_quota",
    "current_quota",
    "remaining_amount",
    "current_cycle",
    "effective_speed",
    "required_speed",
}


def test_no_table_stores_forbidden_derived_columns():
    inspector = inspect(engine)
    for table_name in inspector.get_table_names():
        if table_name == "alembic_version":
            continue
        column_names = {col["name"] for col in inspector.get_columns(table_name)}
        offending = column_names & FORBIDDEN_COLUMN_NAMES
        assert not offending, f"{table_name} に派生値カラムが存在する: {offending}"
