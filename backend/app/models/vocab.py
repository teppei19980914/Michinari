"""単語帳（開発Todo_単語帳_v1.0 要件A）のモデル。

VocabDeck: 資格試験の目標に紐づくデッキ本体。目標削除時はCASCADEで連動削除する
（`recap_theme.goal_id`・`milestone.goal_id`と同じ直接CASCADE方式、開発Todo §0 U1）。
VocabCard: デッキに属するカード（用語・意味・別名・補足）。
VocabAnswerLog: 単語帳の問題集（AI非依存）での解答履歴のみ。今日の復習（要件B）での
解答はここへ記録しない（開発Todo §0 U4）。正答数・誤答数・正答率・連続誤答数は
保存せず、本テーブルから都度算出する（開発Todo §0 U6）。
VocabTermSuggestion: 日次報告の日記（学んだこと）から抜き出した用語候補（要件D）。
目標削除時はCASCADEで連動削除する（`VocabDeck`と同じ目標への直接CASCADE方式）。
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import VocabQuizMode, VocabTermSuggestionStatus
from app.models.base import Base, CreatedAtMixin, TimestampMixin


class VocabDeck(TimestampMixin, Base):
    __tablename__ = "vocab_deck"
    __table_args__ = (Index("ix_vocab_deck_goal_id", "goal_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: 今日の復習の問題作りと、AIフィードバックで、この単語帳の用語を使うか（要件B・C用。
    #: 列は要件Aで作成する）。
    use_in_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class VocabCard(TimestampMixin, Base):
    __tablename__ = "vocab_card"
    __table_args__ = (Index("ix_vocab_card_deck_id", "deck_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deck_id: Mapped[int] = mapped_column(
        ForeignKey("vocab_deck.id", ondelete="CASCADE"), nullable=False
    )
    term: Mapped[str] = mapped_column(Text, nullable=False)
    meaning: Mapped[str] = mapped_column(Text, nullable=False)
    #: 別名・読み（任意）。JSON列の前例が無いため改行区切りのTextとする（利用者プロンプトの決定）。
    aliases: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class VocabAnswerLog(CreatedAtMixin, Base):
    __tablename__ = "vocab_answer_log"
    __table_args__ = (Index("ix_vocab_answer_log_card_id", "card_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(
        ForeignKey("vocab_card.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[VocabQuizMode] = mapped_column(
        Enum(VocabQuizMode, native_enum=False, validate_strings=True), nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class VocabTermSuggestion(TimestampMixin, Base):
    __tablename__ = "vocab_term_suggestion"
    __table_args__ = (
        UniqueConstraint("goal_id", "term_key", name="uq_vocab_term_suggestion_goal_term_key"),
        Index("ix_vocab_term_suggestion_goal_id", "goal_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id", ondelete="CASCADE"), nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    term: Mapped[str] = mapped_column(Text, nullable=False)
    #: 照合用の正規化キー（`question_safety.normalize_for_match`適用後）。重複提案の防止
    #: （開発Todo §0.8 D-U5）に使う照合専用の値であり、成績等の派生値ではない。
    term_key: Mapped[str] = mapped_column(Text, nullable=False)
    source_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[VocabTermSuggestionStatus] = mapped_column(
        Enum(VocabTermSuggestionStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=VocabTermSuggestionStatus.PENDING,
    )
