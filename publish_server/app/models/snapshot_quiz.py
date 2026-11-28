"""公開問題スナップショット（データモデル3章 published_quiz_question、D-01・D-03・D-07）。

D-03により、公開する問題はローカルの`quiz_question.vocab_card_id`が入っている行のみ
（`theme_id`由来は対象外。このフィルタはローカル側＝アップロード元の責務で行い、ここでは
受け取ったデータをそのまま保存する）。

`correct_choice_index`・`explanation`は回答完了まで応答に含めない（D-07、API層・スキーマ層
（`app/schemas/quiz.py`の`QuizQuestionPreview`）で制御する）。

アップロード（`PUT /publish/quiz/{local_deck_id}`）は、この単語帳デッキに紐づく既存の問題行を
全削除してから新規行として挿入する（update-in-placeではなく削除＋再作成）。これにより、
差し替え後は古い版の問題IDが必ず無効化される（単位2テスト観点「差し替え後に古い版の問題へ
回答できないこと」）。回答履歴（`quiz_answer_record`）への影響は`question_id`の
`ondelete="SET NULL"`で吸収する（既存ローカルの`QuizAnswerLog.question_id`と同じ方式）。

`sqlite_autoincrement=True`：全行削除直後に再挿入すると、SQLiteは既定では削除前と同じ
rowid（1から）を再利用してしまい、「差し替え後は古い版の問題IDが必ず無効化される」という
設計が崩れる（PostgreSQL本番のSERIAL/IDENTITYはシーケンスが削除で巻き戻らないため元々
発生しない。テストがSQLiteのため顕在化、単位2実装時に発覚）。この指定でAUTOINCREMENT
キーワードを使わせ、削除済みのrowidを再利用させない。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class PublishedQuizQuestion(Base):
    __tablename__ = "published_quiz_question"
    __table_args__ = (
        Index("ix_published_quiz_question_deck", "vocab_deck_snapshot_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("publish_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vocab_deck_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("published_vocab_deck.id", ondelete="CASCADE"), nullable=False
    )
    #: ローカル側`quiz_question.id`（D-23により外部キー制約は張らない。単位5でのローカル
    #: 取込時の照合キーに使う想定）。
    local_question_id: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    #: `{"choice_1": ..., "choice_2": ..., "choice_3": ..., "choice_4": ...}`のJSON。
    choices_json: Mapped[str] = mapped_column(Text, nullable=False)
    correct_choice_index: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
