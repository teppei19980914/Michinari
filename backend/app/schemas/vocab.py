"""単語帳（開発Todo_単語帳_v1.0 要件A）のAPIスキーマ。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from app.constants.enums import VocabQuizMode


class VocabDeckRead(BaseModel):
    id: int
    goal_id: int
    name: str
    description: str | None
    use_in_ai: bool
    display_order: int
    card_count: int


class VocabDeckCreateRequest(BaseModel):
    name: str
    description: str | None = None


class VocabDeckUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    use_in_ai: bool | None = None


class VocabDeckReorderRequest(BaseModel):
    ordered_deck_ids: list[int]


class VocabCardRead(BaseModel):
    id: int
    deck_id: int
    term: str
    meaning: str
    aliases: str | None
    note: str | None
    is_checked: bool
    display_order: int
    correct_count: int
    incorrect_count: int
    #: 未解答の場合はNone（画面では「—」表示）。
    accuracy_percent: float | None
    consecutive_incorrect: int
    last_answered_at: dt.datetime | None


class VocabCardCreateRequest(BaseModel):
    term: str
    meaning: str
    aliases: str | None = None
    note: str | None = None


class VocabCardUpdateRequest(BaseModel):
    term: str | None = None
    meaning: str | None = None
    aliases: str | None = None
    note: str | None = None


class VocabCardCheckRequest(BaseModel):
    is_checked: bool


class VocabImportPreviewRequest(BaseModel):
    text: str


class VocabImportRowRead(BaseModel):
    line_number: int
    term: str
    meaning: str
    aliases: str | None
    note: str | None


class VocabImportErrorRead(BaseModel):
    line_number: int
    reason: str


class VocabImportPreviewRead(BaseModel):
    rows: list[VocabImportRowRead]
    errors: list[VocabImportErrorRead]
    duplicate_count: int


class VocabImportConfirmRow(BaseModel):
    term: str
    meaning: str
    aliases: str | None = None
    note: str | None = None


class VocabImportConfirmRequest(BaseModel):
    rows: list[VocabImportConfirmRow]


class VocabImportConfirmRead(BaseModel):
    created_count: int


class VocabExportRead(BaseModel):
    text: str


class VocabQuizSessionRequest(BaseModel):
    mode: VocabQuizMode
    #: ALL/CHECKED/EVER_WRONG/CONSECUTIVE_WRONG/WEAK/UNANSWERED
    filter: str = "ALL"
    #: RANDOM/WEAK_ORDER/REGISTERED
    order: str = "RANDOM"
    question_count: int


class VocabQuizOptionRead(BaseModel):
    card_id: int
    text: str


class VocabQuizQuestionRead(BaseModel):
    card_id: int
    prompt: str
    #: カードをめくる形式のみ、出題時点で答えを返す（仕様上の明示的な例外）。
    reveal: str | None = None
    #: 4択のみ。
    options: list[VocabQuizOptionRead] | None = None


class VocabQuizSessionRead(BaseModel):
    questions: list[VocabQuizQuestionRead]
    #: 4択で、誤答選択肢が3つ作れずに出題から外したカード数。
    excluded_count: int


class VocabAnswerRequest(BaseModel):
    mode: VocabQuizMode
    #: カードをめくる形式：利用者の自己判定。
    self_judged_correct: bool | None = None
    #: 入力式：サーバー側で判定する解答文字列。
    answer_text: str | None = None
    #: 4択：選んだ選択肢のカードID。
    selected_card_id: int | None = None


class VocabAnswerResultRead(BaseModel):
    is_correct: bool
