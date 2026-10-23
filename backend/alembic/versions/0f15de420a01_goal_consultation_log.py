"""goal_consultation_log: 目標相談チャットの質疑履歴テーブルを新設する（開発Todo v1.1 V6）

既存の`chat_message`は使わず新規テーブルとする（`daily_record_id`がNOT NULLで日付に
紐づく構造のため、日付を問わないアドホックな1問1答と馴染まないため。開発Todo
`開発Todo_目標相談チャット_v1.1.md` §0「比較」参照）。新規`create_table`のみのため、
既存データに対する安全性テストは対象外（CODING_RULES.md）。

Revision ID: 0f15de420a01
Revises: 9d3d5631a940
Create Date: 2026-10-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0f15de420a01"
down_revision: Union[str, Sequence[str], None] = "9d3d5631a940"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ANSWER_STATUS_ENUM_VALUES = ("ANSWERED", "UNAVAILABLE")


def upgrade() -> None:
    op.create_table(
        "goal_consultation_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "answer_status",
            sa.Enum(*_ANSWER_STATUS_ENUM_VALUES, name="goalconsultationanswerstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("answer_body", sa.Text(), nullable=False),
        sa.Column("cited_dates", sa.Text(), nullable=False),
        sa.Column("cited_weeks", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goal.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_goal_consultation_log_goal_id", "goal_consultation_log", ["goal_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_goal_consultation_log_goal_id", table_name="goal_consultation_log")
    op.drop_table("goal_consultation_log")
