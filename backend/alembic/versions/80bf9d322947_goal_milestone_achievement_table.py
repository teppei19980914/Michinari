"""goal_milestone_achievement_table: 節目のお祝い機能の新規1テーブル
（開発Todo_節目のお祝い_v1.0）。

goal_milestone_achievement（目標が節目に到達した事実の履歴）を新設する。新規
create_tableのみで既存データ移行は発生しない（CODING_RULES.md「DBマイグレーションの
テスト」の対象外）。既存利用者向けの初回バックフィル（開発Todo §0 M9）はここでは行わず、
起動時処理（app/main.py の bootstrap_database）側で業務ロジックとして実行する
（マイグレーションはスキーマ変更のみに留める既存の方針）。

Revision ID: 80bf9d322947
Revises: 4e665f950a10
Create Date: 2026-11-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80bf9d322947'
down_revision: Union[str, Sequence[str], None] = '4e665f950a10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "goal_milestone_achievement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), nullable=False),
        sa.Column(
            "milestone_type",
            sa.Enum(
                "CONSECUTIVE_DAYS",
                "TOTAL_RECORD_DAYS",
                "READING_TOTAL_PAGES",
                "READING_COMPLETED_BOOKS",
                "EXAM_MATERIAL_CYCLE_COMPLETED",
                "EXAM_OVERALL_PROGRESS",
                "WORK_RECORD_COUNT",
                "WORK_EVALUATION_PERIOD_COMPLETED",
                name="milestonetype",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("milestone_key", sa.String(length=100), nullable=False),
        sa.Column("achieved_at", sa.DateTime(), nullable=False),
        sa.Column("celebrated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goal.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "goal_id", "milestone_type", "milestone_key", name="uq_goal_milestone_achievement"
        ),
    )
    op.create_index(
        "ix_goal_milestone_achievement_goal_id",
        "goal_milestone_achievement",
        ["goal_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_goal_milestone_achievement_goal_id", table_name="goal_milestone_achievement"
    )
    op.drop_table("goal_milestone_achievement")
