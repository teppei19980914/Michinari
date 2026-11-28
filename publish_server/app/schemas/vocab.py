"""単語帳公開API・閲覧APIのリクエスト・レスポンススキーマ（単位2）。

文字数上限はpydantic層で検証する（D-20）。`card_type`はローカルの`VocabCardType`を
検証せずそのまま文字列として受け取る（`app/schemas/gantt.py`と同じ方針、D-06・D-23）。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings

_MAX_FIELD_CHARS = get_settings().max_field_chars


class VocabCardIn(BaseModel):
    #: ローカル側`vocab_card.id`（D-23により外部キー制約は張らない）。
    local_card_id: int
    card_type: str = Field(max_length=_MAX_FIELD_CHARS)
    term: str = Field(max_length=_MAX_FIELD_CHARS)
    meaning: str = Field(max_length=_MAX_FIELD_CHARS)
    aliases: str | None = Field(default=None, max_length=_MAX_FIELD_CHARS)
    note: str | None = Field(default=None, max_length=_MAX_FIELD_CHARS)
    situation_text: str | None = Field(default=None, max_length=_MAX_FIELD_CHARS)
    question_text: str | None = Field(default=None, max_length=_MAX_FIELD_CHARS)
    display_order: int


class VocabDeckUploadRequest(BaseModel):
    deck_name: str = Field(max_length=_MAX_FIELD_CHARS)
    cards: list[VocabCardIn]


class VocabDeckListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    local_deck_id: int
    deck_name: str
    card_count: int
    updated_at: datetime


class VocabDeckDetail(BaseModel):
    id: int
    local_deck_id: int
    deck_name: str
    cards: list[VocabCardIn]
    updated_at: datetime
