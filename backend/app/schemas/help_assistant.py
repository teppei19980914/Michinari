"""ヘルプAIアシスタントのリクエスト・レスポンススキーマ（Phase43、仕様書6.18）。

回答の文言はバックエンドで持たない。画面は `status` に応じて `ja.json` の文言を出す。
"""

from pydantic import BaseModel, ConfigDict

from app.constants.enums import HelpAnswerStatus


class HelpAssistantQuestionRequest(BaseModel):
    """質問。長さの上限は `ai.help_question_max_chars` で検証する（サービス層）。"""

    question: str


class HelpSectionRef(BaseModel):
    """出典として示すヘルプのセクション（ID と見出し）。"""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str


class HelpAssistantAnswerRead(BaseModel):
    """回答。`answer` は ANSWERED のときだけ入る。`sections` は検証済みの出典。"""

    status: HelpAnswerStatus
    answer: str | None
    sections: list[HelpSectionRef]


class HelpAssistantLimitsRead(BaseModel):
    """画面が表示・検証に使う上限（app_setting の値）。"""

    max_question_chars: int
