"""consolidate vocab decks per goal (開発Todo_単語帳_出題導線改修_v1.0 U9・U10・D3)

Revision ID: f9acb1463cf0
Revises: 68a52f450ee0
Create Date: 2026-11-26 00:00:00.000000

単語帳（デッキ）をユーザーから隠し、1目標（EXAM）＝1単語帳に統一する。新規のテーブル・
カラムは追加しない、純粋なデータ移行のみのマイグレーション。

- 複数のvocab_deckを持つEXAM目標：display_order→id昇順で最初の1件を残し、残りの
  デッキに属するvocab_cardを`deck_id`の付け替え（UPDATE）でそこへ統合してから、
  余ったデッキ自体を削除する。vocab_card・vocab_answer_logは一切削除しない。
  統合先（最初のデッキ）のuse_in_ai・description等の値はそのまま残し、削除される側の
  値は引き継がない（どちらを優先しても利用者には見えなくなる設定であり、最小限の実装を
  優先する、CLAUDE.md「設計しない」原則）。
- デッキが0件のEXAM目標：目標名をそのままデッキ名としてデッキを1件新規作成する
  （`goal_service.create_goal`が新規目標に対して行うのと同じ初期状態に揃える）。
- READING/WORK目標はそもそもvocab_deckを持ちえない（`vocab_service.create_deck`が
  EXAM以外を拒否するアプリ側のガードのみで保証されており、DB制約ではない）ため対象外。
  本マイグレーションもEXAM目標のみを対象にする（対象外データへ影響しないことをテストで
  確認する、開発Todo_単語帳_出題導線改修_v1.0 §2 脅威モデルのMitigate項目）。

downgradeはデータ移行を巻き戻さない（複数デッキへの分割先が一意に定まらないため）。
新規テーブル・カラムが無いためschema上のdowngradeも不要（no-op）。
"""

import datetime as dt
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f9acb1463cf0"
down_revision: Union[str, Sequence[str], None] = "68a52f450ee0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: SQLAlchemyのDateTime列へ生SQLで書き込む際の表記（f2b7c4a91d3eと同じ理由）。
_DATETIME_STORAGE_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def _consolidate_vocab_decks(connection: sa.Connection) -> None:
    exam_goals = connection.execute(
        sa.text("SELECT id, name FROM goal WHERE category = 'EXAM'")
    ).fetchall()
    if not exam_goals:
        return

    now = dt.datetime.now(dt.UTC).strftime(_DATETIME_STORAGE_FORMAT)
    for goal in exam_goals:
        decks = connection.execute(
            sa.text(
                "SELECT id FROM vocab_deck WHERE goal_id = :goal_id ORDER BY display_order, id"
            ),
            {"goal_id": goal.id},
        ).fetchall()

        if not decks:
            connection.execute(
                sa.text(
                    "INSERT INTO vocab_deck"
                    " (goal_id, name, description, use_in_ai, display_order,"
                    "  created_at, updated_at)"
                    " VALUES (:goal_id, :name, NULL, 1, 0, :now, :now)"
                ),
                {"goal_id": goal.id, "name": goal.name, "now": now},
            )
            continue

        if len(decks) == 1:
            continue

        primary_id = decks[0].id
        extra_ids = [row.id for row in decks[1:]]
        placeholders = ", ".join(f":extra_id{i}" for i in range(len(extra_ids)))
        params: dict[str, object] = {
            f"extra_id{i}": extra_id for i, extra_id in enumerate(extra_ids)
        }
        connection.execute(
            sa.text(
                f"UPDATE vocab_card SET deck_id = :primary_id WHERE deck_id IN ({placeholders})"
            ),
            {**params, "primary_id": primary_id},
        )
        connection.execute(
            sa.text(f"DELETE FROM vocab_deck WHERE id IN ({placeholders})"),
            params,
        )


def upgrade() -> None:
    """Upgrade schema."""
    _consolidate_vocab_decks(op.get_bind())


def downgrade() -> None:
    """Downgrade schema.

    データ移行のみのため、schema側の変更は無い（no-op）。統合・自動作成したデッキの
    分割・削除は、どのカードが元々どのデッキに属していたかという情報が統合時点で
    失われるため復元できない。
    """
