"""案件情報モデル（設計書 データ構造編 5.3「work_assignment（案件情報）」）。

category=WORKのgoalに対し、exam_subjectとmaterialを統合した位置づけの
子テーブルとして1件登録する（goal_idにUNIQUE制約＝1目標1案件、要件定義書R-72）。
bookと異なりdue_dateは持たない（仕事の案件は納期未定のことが多く、読書の読了目標日
のような必須の外部制約が存在しないため。要件定義書R-73）。
案件の終了（成果あり／なし）はgoal.statusで表現するため、独自のstatus/completed_at
は持たない。
"""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.goal import Goal
    from app.models.record import WorkLog


class WorkAssignment(TimestampMixin, Base):
    """案件情報。expected_contentは登録後も更新可能で、更新は上書き（変更履歴なし）。"""

    __tablename__ = "work_assignment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(
        ForeignKey("goal.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    client_name: Mapped[str | None] = mapped_column(String, nullable=True)
    expected_content: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)

    goal: Mapped["Goal"] = relationship(back_populates="work_assignment")
    # work_assignment -> work_log は RESTRICT（業務記録が残る案件は削除不可、book/material
    # と同じ方針。データ構造編5.3）。
    work_logs: Mapped[list["WorkLog"]] = relationship(
        back_populates="work_assignment", passive_deletes=True
    )
