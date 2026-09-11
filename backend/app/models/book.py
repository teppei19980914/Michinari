"""書籍モデル（設計書 データ構造編 5.3）。

category=READINGのgoalに対し、exam_subjectとmaterialを統合した位置づけの
子テーブルとして1件登録する（goal_idにUNIQUE制約＝1目標1冊）。
読了・中断はgoal.statusで表現するため、独自のstatus/completed_atは持たない。
"""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.models.goal import Goal
    from app.models.record import ReadingLog


class Book(TimestampMixin, Base):
    """書籍。due_dateはexam_subjectと異なり自動導出せず、常に利用者が直接入力する。

    total_pages は必須（NOT NULL）。読書進捗（ロジック・プロンプト編21.2）の進捗率を常に算出できる
    ためであり、「総ページ数が未入力の書籍ではページ進捗を表示しない」という旧仕様
    （要件定義書R-70 改訂前）を廃止した結果である（仕様変更2026-09-11）。
    """

    __tablename__ = "book"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(
        ForeignKey("goal.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    goal: Mapped["Goal"] = relationship(back_populates="book")
    # book -> reading_log は RESTRICT（想起記録が残る書籍は削除不可、material と同じ方針）。
    reading_logs: Mapped[list["ReadingLog"]] = relationship(
        back_populates="book", passive_deletes=True
    )
