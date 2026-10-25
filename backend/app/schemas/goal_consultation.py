"""目標相談チャットのリクエスト・レスポンススキーマ（S09、要件定義書R-104。S10で履歴の
スキーマを追加、S11で会話継続のスキーマを追加）。

回答の文言はバックエンドで持たない。画面は`status`に応じて`ja.json`の文言を出す
（`help_assistant.py`と同じ方針）。
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.constants.enums import GoalConsultationAnswerStatus


class GoalConsultationQuestionRequest(BaseModel):
    """質問。長さの上限は`ai.goal_consultation_question_max_chars`で検証する（サービス層）。
    `conversation_id`はどの会話への質問かを明示する（S11、開発Todo v1.2 W7。省略時に
    暗黙で最新会話を使う、という曖昧さを避けるため必須にする）。`attachment_ids`は利用者が
    選択した添付ファイル（開発Todo_添付ファイル機能_v1.0 A1、goal非依存の共通プール）。
    """

    conversation_id: int
    question: str
    attachment_ids: list[int] = []


class GoalConsultationConversationCreateRequest(BaseModel):
    """新しい会話の開始（S11、開発Todo v1.2 W7）。`title`は省略可（既定は空文字、
    画面側で既定文言を表示する）。"""

    title: str = ""


class GoalConsultationConversationRead(BaseModel):
    """会話一覧・作成結果の1件（S11、開発Todo v1.2 W7）。"""

    id: int
    title: str
    created_at: datetime


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
    """相談履歴の1件（S10、開発Todo v1.1 V7。S11で`conversation_id`を追加）。"""

    id: int
    conversation_id: int
    question: str
    status: GoalConsultationAnswerStatus
    answer: str | None
    cited_dates: list[date]
    cited_weeks: list[GoalConsultationCitedWeek]
    created_at: datetime
