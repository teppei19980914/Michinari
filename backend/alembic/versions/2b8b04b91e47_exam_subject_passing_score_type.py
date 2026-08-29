"""exam_subject: add passing_score_type / passing_score_max columns (data structure doc 5.3)

Revision ID: 2b8b04b91e47
Revises: a3f9c1d7e2b4
Create Date: 2026-08-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b8b04b91e47'
down_revision: Union[str, Sequence[str], None] = 'a3f9c1d7e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    passing_score_typeのserver_defaultは意図的に残す（削除しない）。SQLiteは
    render_as_batch=True（env.py）でカラム追加をテーブル再作成＋データコピーとして
    実行するため、同一batch_alter_table内でserver_defaultを追加後に削除すると、
    再作成後のテーブル定義からデフォルトが消えた状態でコピーが行われ、既存行に対する
    INSERT ... SELECTがNOT NULL制約違反になる（新規列に値もデフォルトも無いため）。
    ORM層はPassingScoreType.PERCENTAGEというPython側defaultを別途持つため、
    server_defaultを残しても実害はない。
    """
    with op.batch_alter_table('exam_subject', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'passing_score_type',
                sa.String(),
                nullable=False,
                server_default='PERCENTAGE',
            )
        )
        batch_op.add_column(sa.Column('passing_score_max', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('exam_subject', schema=None) as batch_op:
        batch_op.drop_column('passing_score_max')
        batch_op.drop_column('passing_score_type')
