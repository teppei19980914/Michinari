"""復習クイズ（開発Todo_復習クイズ_v1.0）のモデル。

QuizQuestion: 振り返り（テーマ累積、`RecapTheme`）から生成したクイズ本体と、現在の
間隔進行状態（1:1のため分割しない）。テーマの改名・統合・再構築時は未出題（未回答）の
行を削除し、作り直す対象とする（開発Todo §0 U3）。
QuizAnswerLog: 解答履歴（分析用）。テーマの改名・再構築で対応する`QuizQuestion`行が
削除されても、`theme_id`はそのまま残るため分析（正答率の推移）を継続できる
（開発Todo §0 D4）。
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class QuizQuestion(CreatedAtMixin, Base):
    __tablename__ = "quiz_question"
    __table_args__ = (
        Index("ix_quiz_question_theme_id", "theme_id"),
        Index("ix_quiz_question_next_due_date", "next_due_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[int] = mapped_column(
        ForeignKey("recap_theme.id", ondelete="CASCADE"), nullable=False
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    choice_1: Mapped[str] = mapped_column(Text, nullable=False)
    choice_2: Mapped[str] = mapped_column(Text, nullable=False)
    choice_3: Mapped[str] = mapped_column(Text, nullable=False)
    choice_4: Mapped[str] = mapped_column(Text, nullable=False)
    #: 正解の選択肢（0〜3、choice_1〜choice_4に対応）。
    correct_choice_index: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    #: 出典（元になった報告の日付）。生成時に実在する報告の日付であることを検証済み。
    citation_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: `quiz.interval_days`の何番目の間隔か（0始まり）。
    interval_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: 次回出題予定日（生成直後は生成日＝即時出題可能）。
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: 一度でも解答されたか（NULL＝未出題）。利用者操作による「作り直す」は未出題の行のみを
    #: 削除し、既に解答済み（進行中）の行は残す（開発Todo §0 U3と区別。テーマの改名・統合・
    #: 再構築、目標のアーカイブ・削除は解答済みを含め全行を削除する）。
    last_answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class QuizAnswerLog(CreatedAtMixin, Base):
    __tablename__ = "quiz_answer_log"
    __table_args__ = (Index("ix_quiz_answer_log_theme_id", "theme_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[int] = mapped_column(
        ForeignKey("recap_theme.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("quiz_question.id", ondelete="SET NULL"), nullable=True
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
