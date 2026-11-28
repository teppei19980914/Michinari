"""Web回答履歴（データモデル3章 quiz_answer_record、D-07・D-08・D-21）。

正誤判定はサーバ側で行い、判定結果（`is_correct`）を記録する（D-07）。`question_id`は
`published_quiz_question`への参照だが、差し替え（単位2設計、削除＋再作成）で元の問題行が
消えても履歴自体は残す（`ondelete="SET NULL"`、既存ローカルの`QuizAnswerLog.question_id`と
同じ方式）。そのため、単位5（任意）でのローカル取込時の照合キーには`question_id`ではなく
`local_question_id`（回答時点の`PublishedQuizQuestion.local_question_id`を複写した値）を使う
（開発Todo_Web公開_v1.0 6.1節「ローカル取込時の照合キーとして`local_question_id`・
`answered_at`を使う」）。

`client_answer_uuid`は冪等性制御（同じ回答の再送で重複記録しない、STRIDE分析5章
「大量回答リクエストによるDB肥大化」対策）に使うため一意制約を持つ。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class QuizAnswerRecord(CreatedAtMixin, Base):
    __tablename__ = "quiz_answer_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("publish_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("published_quiz_question.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: 単位5でのローカル取込時の照合キー（6.1節参照、`question_id`がSET NULLされても残る）。
    local_question_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chosen_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    client_answer_uuid: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
