"""復習クイズのAPIスキーマ（開発Todo_復習クイズ_v1.0、仕様書6.1.6。開発Todo_単語帳_v1.0
要件Bで出所（テーマ／単語帳）の区別を追加）。
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

#: 問題の出所（B-U1。今日の復習の材料はテーマ由来・単語帳由来の2つ）。
QuizSource = Literal["theme", "vocab"]


class QuizQuestionRead(BaseModel):
    """出題用（正解・解説・出典は含めない。事前に見えると解答にならないため）。

    出所に応じて`theme_*`／`vocab_deck_*`のどちらか一方のみが入る（他方はNone）。
    """

    id: int
    source: QuizSource
    theme_id: int | None = None
    theme_name: str | None = None
    vocab_deck_id: int | None = None
    vocab_deck_name: str | None = None
    question_text: str
    choices: list[str]


class QuizAnswerRequest(BaseModel):
    choice_index: int = Field(ge=0, le=3)


class QuizAnswerResultRead(BaseModel):
    """解答結果。出所に応じて出典の表示が異なる（テーマ由来＝`citation_date`、単語帳由来＝
    `vocab_deck_id`・`vocab_deck_name`、画面はこちらで「単語帳で確認する」リンクを出す）。
    """

    is_correct: bool
    correct_choice_index: int
    explanation: str
    source: QuizSource
    citation_date: dt.date | None = None
    vocab_deck_id: int | None = None
    vocab_deck_name: str | None = None
    next_due_date: dt.date


class QuizGenerateResultRead(BaseModel):
    created: int
