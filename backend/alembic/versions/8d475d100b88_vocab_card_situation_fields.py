"""vocab_card_situation_fields: シチュエーションカードの列追加（開発Todo_単語帳_v1.0 要件F）

Revision ID: 8d475d100b88
Revises: e9eca0569d7c
Create Date: 2026-11-23 10:30:00.000000

vocab_cardへ`card_type`（TERM/SITUATION、既定TERM）・`situation_text`（NULL可）・
`question_text`（NULL可）の3列を追加する。既存の`term`・`meaning`のNOT NULL制約・
CHECK制約は変更しない（列追加のみ）。既存の全行は`card_type`の`server_default`により
TERMになる（F-D21、要件に明記された「既存のカードがすべて用語になること」を満たす）。

列追加のみのため、CODING_RULES.md「DBマイグレーションのテスト」に従い、既存データ
（用語カード・解答履歴）が入った状態でのupgrade・downgradeでデータが失われないことを
テストで確認する（test_bootstrap.py）。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d475d100b88"
down_revision: Union[str, Sequence[str], None] = "e9eca0569d7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("vocab_card", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "card_type",
                sa.Enum("TERM", "SITUATION", name="vocabcardtype", native_enum=False),
                nullable=False,
                server_default="TERM",
            )
        )
        batch_op.add_column(sa.Column("situation_text", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("question_text", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema.

    シチュエーションカードは旧スキーマには表現できない概念だが、term/meaning/note列は
    既に埋まっているため行の削除は行わず、3列を削除するのみとする（データの消失は
    situation_text・question_text・card_typeの値のみで、用語カードは完全に保持される）。
    """
    with op.batch_alter_table("vocab_card", schema=None) as batch_op:
        batch_op.drop_column("question_text")
        batch_op.drop_column("situation_text")
        batch_op.drop_column("card_type")
