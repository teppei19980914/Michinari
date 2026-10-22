"""目標相談チャットのリクエスト・レスポンススキーマ（S09、要件定義書R-104。S10で履歴の
スキーマを追加）。

回答の文言はバックエンドで持たない。画面は`status`に応じて`ja.json`の文言を出す
（`help_assistant.py`と同じ方針）。
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.constants.enums import GoalConsultationAnswerStatus


class GoalConsultationQuestionRequest(BaseModel):
    """質問。長さの上限は`ai.goal_consultation_question_max_chars`で検証する（サービス層）。"""

    question: str


class GoalConsultationCitedWeek(BaseModel):
    """根拠として示す週次要約の週（開始日・終了日）。"""

    model_config = ConfigDict(frozen=True)

    start: date
    end: date


class GoalConsultationAnswerRead(BaseModel):
    """回答。`answer`はANSWEREDのときだけ入る。`cited_dates`／`cited_weeks`は検証済みの根拠
    （プロンプトに実際に含めた日付・週だけを採用、開発Todo U10）。
    """

    status: GoalConsultationAnswerStatus
    answer: str | None
    cited_dates: list[date]
    cited_weeks: list[GoalConsultationCitedWeek]


class GoalConsultationLimitsRead(BaseModel):
    """画面が表示・検証に使う上限（app_settingの値）。"""

    max_question_chars: int


class GoalConsultationHistoryItemRead(BaseModel):
    """相談履歴の1件（S10、開発Todo v1.1 V7）。"""

    id: int
    question: str
    status: GoalConsultationAnswerStatus
    answer: str | None
    cited_dates: list[date]
    cited_weeks: list[GoalConsultationCitedWeek]
    created_at: datetime
