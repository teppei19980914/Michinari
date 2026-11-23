"""単語帳（開発Todo_単語帳_v1.0 要件A）のAPIスキーマ。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from app.constants.enums import VocabCardType, VocabQuizMode


class VocabDeckRead(BaseModel):
    id: int
    goal_id: int
    name: str
    description: str | None
    use_in_ai: bool
    display_order: int
    card_count: int
    #: 習得済みカード数（開発Todo_単語帳_v1.0 要件E E-U6、都度算出）。
    mastered_card_count: int
    #: 用語カードの件数・習得済み件数（開発Todo_単語帳_v1.0 要件F F-U9、「用語◯語／場面◯件」
    #: の表示用、都度算出）。
    term_card_count: int
    term_mastered_card_count: int
    #: シチュエーションカードの件数・習得済み件数（同上、F-U9）。
    situation_card_count: int
    situation_mastered_card_count: int
    #: 出題セッションの問題数の初期値（`vocab.session_default_questions`、設定画面には表示
    #: しない内部パラメータ。不具合修正、2026-11-22）。
    session_default_questions: int
    #: 出題セッションの問題数の上限（`vocab.session_max_questions`、同上）。
    session_max_questions: int


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
    #: カードの種類（開発Todo_単語帳_v1.0 要件F）。作成後は不変（F-D2）。
    card_type: VocabCardType
    term: str
    meaning: str
    aliases: str | None
    note: str | None
    #: シチュエーションカード専用（要件F）。TERMでは常にNone。
    situation_text: str | None
    question_text: str | None
    is_checked: bool
    display_order: int
    correct_count: int
    incorrect_count: int
    #: 未解答の場合はNone（画面では「—」表示）。
    accuracy_percent: float | None
    consecutive_incorrect: int
    last_answered_at: dt.datetime | None
    #: 習得済みか（開発Todo_単語帳_v1.0 要件E E-U1、都度算出）。
    is_mastered: bool


class VocabCardCreateRequest(BaseModel):
    #: 既定はTERM（既存A〜Dの挙動を保つ）。作成後は変更できない（F-D2）。
    card_type: VocabCardType = VocabCardType.TERM
    term: str
    meaning: str
    aliases: str | None = None
    note: str | None = None
    situation_text: str | None = None
    question_text: str | None = None


class VocabCardUpdateRequest(BaseModel):
    #: card_typeを持たない（開発Todo_単語帳_v1.0 要件F F-D2、作成後の種類変更を
    #: スキーマレベルで不可能にする）。
    term: str | None = None
    meaning: str | None = None
    aliases: str | None = None
    note: str | None = None
    situation_text: str | None = None
    question_text: str | None = None


class VocabCardCheckRequest(BaseModel):
    is_checked: bool


class VocabImportPreviewRequest(BaseModel):
    text: str
    #: 取り込む種類（開発Todo_単語帳_v1.0 要件F F-U8）。既定はTERM（既存A〜Dの挙動を保つ）。
    card_type: VocabCardType = VocabCardType.TERM


class VocabImportRowRead(BaseModel):
    line_number: int
    term: str
    meaning: str
    aliases: str | None
    note: str | None
    situation_text: str | None = None
    question_text: str | None = None


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
    situation_text: str | None = None
    question_text: str | None = None


class VocabImportConfirmRequest(BaseModel):
    rows: list[VocabImportConfirmRow]
    card_type: VocabCardType = VocabCardType.TERM


class VocabImportConfirmRead(BaseModel):
    created_count: int


class VocabExportRead(BaseModel):
    text: str


class VocabQuizSessionRequest(BaseModel):
    #: TERMカードの出題形式。SITUATIONカードは常にFLASH_SITUATION（開発Todo_単語帳_v1.0
    #: 要件F F-D8、「両方」選択時は問題ごとに実際の形式が異なる）。
    mode: VocabQuizMode
    #: ALL/CHECKED/EVER_WRONG/CONSECUTIVE_WRONG/WEAK/UNANSWERED/UNMASTERED
    filter: str = "ALL"
    #: RANDOM/WEAK_ORDER/REGISTERED
    order: str = "RANDOM"
    question_count: int
    #: カードの種類の絞り込み（ALL/TERM/SITUATION、開発Todo_単語帳_v1.0 要件F F-U3・F-D25）。
    card_type: str = "ALL"


class VocabQuizOptionRead(BaseModel):
    card_id: int
    text: str


class VocabQuizQuestionRead(BaseModel):
    card_id: int
    #: その問題の実際の出題形式（開発Todo_単語帳_v1.0 要件F F-D7、「両方」選択時は
    #: カードごとに異なる）。
    mode: VocabQuizMode
    prompt: str
    #: カードをめくる形式のみ、出題時点で答えを返す（仕様上の明示的な例外）。
    reveal: str | None = None
    #: FLASH_SITUATIONのみ、解説（登録されていなければNone、F-U4）。
    explanation: str | None = None
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


class VocabTermSuggestionGenerateRequest(BaseModel):
    record_date: dt.date


class VocabTermSuggestionRead(BaseModel):
    id: int
    goal_id: int
    record_date: dt.date
    term: str
    #: 意味の下書き（その用語を含む日記の一文、開発Todo_単語帳_v1.0 要件D D-U2）。
    source_sentence: str


class VocabTermSuggestionListRead(BaseModel):
    suggestions: list[VocabTermSuggestionRead]
    #: 追加先の初期値（その目標で最後に使った単語帳、D-D5）。単語帳が1つも無ければNone。
    default_deck_id: int | None


class VocabTermSuggestionAcceptRequest(BaseModel):
    deck_id: int
    term: str
    meaning: str
    aliases: str | None = None
