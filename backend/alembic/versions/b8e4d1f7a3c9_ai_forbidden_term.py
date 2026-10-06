"""ai_forbidden_term テーブルの新設（ヘルプAIアシスタント、Phase43）

Revision ID: b8e4d1f7a3c9
Revises: 5e0f3b7c2a91
Create Date: 2026-10-06 09:00:00.000000

ヘルプAIアシスタントの禁止語を運用者が管理するための新規テーブル（設計書 データ構造編 5.5、
開発Todo「ヘルプAIアシスタント」）。既存テーブルへの変更は伴わないため、既存データの
保持を確かめるテストは対象外（CODING_RULES.md「DBマイグレーションのテスト」の判断の目安）。
禁止語の初期投入は起動時シード（app/init/seed_data.py）で行う。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8e4d1f7a3c9"
down_revision: Union[str, Sequence[str], None] = "5e0f3b7c2a91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_forbidden_term",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("term", sa.Text(), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_forbidden_term")
