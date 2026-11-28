"""unit3 gantt snapshot holidays: published_gantt_snapshot.holidays_json列追加
（開発Todo_Web公開_v1.0 単位3）。

既存テーブルへの列追加のため、CODING_RULES.md「DBマイグレーションのテスト」の対象
（既存データを保持したまま適用できることを`tests/test_migration_holidays_column.py`で
検証する）。

Revision ID: c47a9e21d8f3
Revises: 93c2ed255fee
Create Date: 2026-11-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c47a9e21d8f3"
down_revision: Union[str, Sequence[str], None] = "93c2ed255fee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("published_gantt_snapshot", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("holidays_json", sa.Text(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("published_gantt_snapshot", schema=None) as batch_op:
        batch_op.drop_column("holidays_json")
