"""問題公開API・閲覧API・回答APIのリクエスト・レスポンススキーマ（単位2）。

`QuizQuestionPreview`は回答前に返すスキーマで、`correct_choice_index`・`explanation`を
意図的に含めない（D-07必須）。回答後の結果は`QuizAnswerResult`で別途返す。

`QuizQuestionIn.local_card_id`は、D-03・STRIDE分析5章「ローカル→公開API」I:情報漏洩
「`theme_id`由来の問題や機微な学習記録が誤って送信される」への対策（「D-03のフィルタを
クライアントだけでなくサーバ側でも二重検証（`vocab_card_id`必須チェック）」）に使う。
ローカル側のフィルタ（`vocab_card_id IS NOT NULL`）はアップロード元の責務だが、サーバ側でも
`app/services/publish_service.py`の`replace_quiz_questions`がこの値を同じ単語帳デッキの
カード一覧（`published_vocab_deck.cards_json`）と照合し、一致しない場合は拒否する。
"""

from pydantic import BaseModel, Field

from app.config import get_settings

_MAX_FIELD_CHARS = get_settings().max_field_chars
#: 4択（choice_1〜choice_4）のため、選択肢インデックスは0〜3のみ許可する。
_MAX_CHOICE_INDEX = 3


class QuizQuestionIn(BaseModel):
    #: ローカル側`quiz_question.id`（D-23により外部キー制約は張らない）。
    local_question_id: int
    #: ローカル側`quiz_question.vocab_card_id`（出所検証用、D-03・STRIDE対策。本モジュールの
    #: docstring参照）。
    local_card_id: int
    question_text: str = Field(max_length=_MAX_FIELD_CHARS)
    choice_1: str = Field(max_length=_MAX_FIELD_CHARS)
    choice_2: str = Field(max_length=_MAX_FIELD_CHARS)
    choice_3: str = Field(max_length=_MAX_FIELD_CHARS)
    choice_4: str = Field(max_length=_MAX_FIELD_CHARS)
    correct_choice_index: int = Field(ge=0, le=_MAX_CHOICE_INDEX)
    explanation: str = Field(max_length=_MAX_FIELD_CHARS)


class QuizQuestionUploadRequest(BaseModel):
    questions: list[QuizQuestionIn]


class QuizQuestionPreview(BaseModel):
    """D-07：回答前のレスポンス。正解番号・解説を含めない。"""

    id: int
    question_text: str
    choice_1: str
    choice_2: str
    choice_3: str
    choice_4: str


class QuizAnswerRequest(BaseModel):
    chosen_index: int = Field(ge=0, le=_MAX_CHOICE_INDEX)
    #: 重複送信対策（冪等性、STRIDE分析5章）。クライアント側で生成したUUID等の一意な値。
    client_answer_uuid: str = Field(min_length=1, max_length=64)


class QuizAnswerResult(BaseModel):
    is_correct: bool
    correct_choice_index: int
    explanation: str
