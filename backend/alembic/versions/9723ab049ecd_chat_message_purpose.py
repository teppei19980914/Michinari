"""add chat_message.purpose (data structure doc 5.4, logic doc 16.3 reading AI separation)

Revision ID: 9723ab049ecd
Revises: b7a1021fff73
Create Date: 2026-08-31 00:00:00.000001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9723ab049ecd'
down_revision: Union[str, Sequence[str], None] = 'b7a1021fff73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    chat_message.purposeのserver_defaultは意図的に残す（削除しない）。2b8b04b91e47・
    b7a1021fff73と同じ理由：SQLiteのバッチテーブル再作成時、同一batch内でserver_default
    を追加後に削除すると既存行のコピーがNOT NULL制約違反になる。既存のchat_messageは
    全てDAILY_FEEDBACK（資格試験用、読書機能導入前は他の用途が無かったため）として
    遡及設定する。ORM層はChatMessage生成時に必ずpurposeを明示するため実害はない。
    """
    with op.batch_alter_table('chat_message', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'purpose', sa.String(), nullable=False, server_default='DAILY_FEEDBACK'
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('chat_message', schema=None) as batch_op:
        batch_op.drop_column('purpose')
