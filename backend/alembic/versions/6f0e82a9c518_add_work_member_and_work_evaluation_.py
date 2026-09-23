"""add work_member and work_evaluation_report tables, work_assignment role column

チームメンバー管理・評価者ロール・AI評価レポート機能（要件定義書6.11）。

work_assignment.role は nullable・server_default なしのため、e1f4a9c3b6d8 の
goal_retrospective 追加列と同じ理由で SQLite batch mode でも安全に追加できる
（既存行は NULL のまま）。

work_member.member_id 側の外部キー（work_evaluation_report.member_id）は
ondelete を指定しない（RESTRICT相当）。評価レポートが存在するメンバーの物理削除は
サービス層（work_member_service.delete_work_member）が明示的に拒否するため、
DBの制約は最終防波堤として機能する。

Revision ID: 6f0e82a9c518
Revises: 7f4f5e089f3a
Create Date: 2026-09-23 12:13:10.903515

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f0e82a9c518"
down_revision: Union[str, Sequence[str], None] = "7f4f5e089f3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("work_assignment", schema=None) as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(), nullable=True))

    op.create_table(
        "work_member",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_assignment_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("gender", sa.String(), nullable=True),
        sa.Column("characteristics", sa.Text(), nullable=True),
        sa.Column("consent_confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["work_assignment_id"], ["work_assignment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("work_member", schema=None) as batch_op:
        batch_op.create_index(
            "ix_work_member_work_assignment_id", ["work_assignment_id"], unique=False
        )

    op.create_table(
        "work_evaluation_report",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_assignment_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("considerations", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("edited_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["work_assignment_id"], ["work_assignment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["work_member.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("work_evaluation_report", schema=None) as batch_op:
        batch_op.create_index("ix_work_evaluation_report_member_id", ["member_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("work_evaluation_report", schema=None) as batch_op:
        batch_op.drop_index("ix_work_evaluation_report_member_id")
    op.drop_table("work_evaluation_report")

    with op.batch_alter_table("work_member", schema=None) as batch_op:
        batch_op.drop_index("ix_work_member_work_assignment_id")
    op.drop_table("work_member")

    with op.batch_alter_table("work_assignment", schema=None) as batch_op:
        batch_op.drop_column("role")
