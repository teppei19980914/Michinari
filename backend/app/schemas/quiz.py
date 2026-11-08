"""復習クイズのAPIスキーマ（開発Todo_復習クイズ_v1.0、仕様書6.1.6）。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class QuizQuestionRead(BaseModel):
    """出題用（正解・解説・出典は含めない。事前に見えると解答にならないため）。"""

    id: int
    theme_id: int
    theme_name: str
    question_text: str
    choices: list[str]


class QuizAnswerRequest(BaseModel):
    choice_index: int = Field(ge=0, le=3)


class QuizAnswerResultRead(BaseModel):
    is_correct: bool
    correct_choice_index: int
    explanation: str
    citation_date: dt.date
    next_due_date: dt.date


class QuizGenerateResultRead(BaseModel):
    created: int
