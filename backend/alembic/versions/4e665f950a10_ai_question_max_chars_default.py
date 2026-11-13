"""ai_question_max_chars_default: ヘルプAIアシスタント・目標相談チャットの質問上限の
既定値を300から500へ引き上げる（利用者依頼、2026-11-01）。

app_settingには`prompt_template.is_customized`のようなカスタマイズ済みフラグが無いため、
「現在値が旧既定値(300)のままの行のみ」を更新する値一致ヒューリスティックで、利用者が
独自の値へ変更済みの行には触れない（2ceb7aa212fcと同じ方針）。500への引き上げは上限を
緩める方向のみのため、このヒューリスティックで取り残される側（独自に300へ変更していた
行が誤って更新されるケース）が起きても実害は小さい。

Revision ID: 4e665f950a10
Revises: 0ab58c423373
Create Date: 2026-11-01 12:21:35.712495

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4e665f950a10"
down_revision: Union[str, Sequence[str], None] = "0ab58c423373"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_DEFAULT = "300"
_NEW_DEFAULT = "500"
_KEYS = ("ai.help_question_max_chars", "ai.goal_consultation_question_max_chars")


def upgrade() -> None:
    """Upgrade schema."""
    for key in _KEYS:
        op.execute(
            sa.text(
                "UPDATE app_setting SET value = :new_value WHERE key = :key AND value = :old_value"
            ).bindparams(new_value=_NEW_DEFAULT, old_value=_OLD_DEFAULT, key=key)
        )


def downgrade() -> None:
    """Downgrade schema."""
    for key in _KEYS:
        op.execute(
            sa.text(
                "UPDATE app_setting SET value = :old_value WHERE key = :key AND value = :new_value"
            ).bindparams(old_value=_OLD_DEFAULT, new_value=_NEW_DEFAULT, key=key)
        )
