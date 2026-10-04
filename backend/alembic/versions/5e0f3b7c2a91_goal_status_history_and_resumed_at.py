"""goal: 再開日の列を追加し、状態遷移履歴テーブル（goal_status_history）を新設する（開発Todo 1-5・1-6）

既存の目標には、現在の状態に至るまでの遷移の記録が無い。そこで既存の時刻列（作成日時・
開始日時・終了日時・更新日時）から、確実に分かる遷移だけを初期履歴として復元する。
  - 作成時点: 下書き（created_at）
  - 開始済み（activated_at がある）: 下書き → 実行中（activated_at）
  - 現在が一時停止: 実行中 → 一時停止（updated_at。最終更新の時刻で近似する）
  - 現在がクローズ済み: 実行中 → クローズ済み（closed_at）

Revision ID: 5e0f3b7c2a91
Revises: 4d9e2a6b1c7f
Create Date: 2026-10-04 00:00:00.000000

"""

from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5e0f3b7c2a91"
down_revision: Union[str, Sequence[str], None] = "4d9e2a6b1c7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GOAL_STATUS_ENUM_VALUES = (
    "DRAFT",
    "ACTIVE",
    "PAUSED",
    "CLOSED_WITH_RESULT",
    "CLOSED_WITHOUT_RESULT",
)


def _goal_status_type() -> sa.Enum:
    return sa.Enum(*_GOAL_STATUS_ENUM_VALUES, name="goalstatus", native_enum=False)


def upgrade() -> None:
    """再開日の列を追加し、履歴テーブルを作って既存の目標の初期履歴を復元する。"""
    op.add_column("goal", sa.Column("resumed_at", sa.DateTime(), nullable=True))
    op.create_table(
        "goal_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("from_status", _goal_status_type(), nullable=True),
        sa.Column("to_status", _goal_status_type(), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goal.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_goal_status_history_goal_id", "goal_status_history", ["goal_id"], unique=False
    )
    _backfill_initial_history()


def _as_datetime(value):
    """生のSQLで読んだ日時は、SQLiteでは文字列のまま返るため、日時へ変換する（NULLはそのまま）。"""
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _backfill_initial_history() -> None:
    """既存の目標の時刻列から、確実に分かる遷移だけを初期履歴として書き込む。"""
    connection = op.get_bind()
    goals = connection.execute(
        sa.text("SELECT id, status, created_at, activated_at, closed_at, updated_at FROM goal")
    ).fetchall()
    history = sa.table(
        "goal_status_history",
        sa.column("goal_id", sa.Integer()),
        sa.column("from_status", sa.String()),
        sa.column("to_status", sa.String()),
        sa.column("changed_at", sa.DateTime()),
    )
    for goal_id, status, created_at, activated_at, closed_at, updated_at in goals:
        created_at, activated_at, closed_at, updated_at = (
            _as_datetime(value) for value in (created_at, activated_at, closed_at, updated_at)
        )
        rows = [(None, "DRAFT", created_at)]
        if activated_at is not None:
            rows.append(("DRAFT", "ACTIVE", activated_at))
        if status == "PAUSED":
            rows.append(("ACTIVE", "PAUSED", updated_at or activated_at or created_at))
        elif status in ("CLOSED_WITH_RESULT", "CLOSED_WITHOUT_RESULT"):
            rows.append(("ACTIVE", status, closed_at or updated_at or created_at))
        for from_status, to_status, changed_at in rows:
            connection.execute(
                history.insert().values(
                    goal_id=goal_id,
                    from_status=from_status,
                    to_status=to_status,
                    changed_at=changed_at,
                )
            )


def downgrade() -> None:
    """履歴テーブルと再開日の列を削除する（履歴の内容は失われる）。"""
    op.drop_index("ix_goal_status_history_goal_id", table_name="goal_status_history")
    op.drop_table("goal_status_history")
    op.drop_column("goal", "resumed_at")
