"""日次記録のリクエスト/レスポンススキーマ（データ構造編5.4・6.2、仕様書6.4〜6.7・14章）。

品質指標（quality_value）は教材の quality_metric_type に応じて入力形式が異なる
（SUBJECTIVEは1〜5、それ以外は0〜100）ため、正規化はサービス層（record_service）で行う。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import AiPurpose, ChatRole, QualityMetricType, RecordState


class SlotMinutesInput(BaseModel):
    """時間枠1件分の投下時間（仕様書6.5「時間枠ごとの投下時間の入力」）。

    配分していない時間枠も指定できる（予定外の空き時間に学習した分を記録できないと、
    投下時間が実態より小さく計上され実効速度が過大に算出されるため）。
    """

    slot_id: int
    minutes: int = Field(ge=0)


class SlotDefaultMinutesRead(BaseModel):
    """日次報告の時間枠別入力欄の既定値（9.2の按分結果）。"""

    slot_id: int
    slot_name: str
    minutes: int


class SlotMinutesRead(BaseModel):
    """投下時間の時間枠別内訳。`slot_id` が NULL の行は、記録後に時間枠が削除されたもの。"""

    slot_id: int | None
    slot_name: str | None
    minutes: int


class StudyLogInput(BaseModel):
    material_id: int
    #: 時間枠ごとの投下時間。教材の投下時間はこの合計とする（R-14）。
    slot_minutes: list[SlotMinutesInput] = Field(default_factory=list)
    amount_completed: float = Field(ge=0)
    cycle_number: int | None = Field(default=None, ge=1)
    quality_value: float | None = None


class StudyLogRead(BaseModel):
    id: int
    material_id: int
    #: 時間枠別入力の合計。1件も入力が無い場合はNone（0ではない、8.4）。
    minutes_spent: int | None
    slot_minutes: list[SlotMinutesRead]
    amount_completed: float
    cycle_number: int
    quality_value: float | None


class ReadingLogInput(BaseModel):
    """読書記録の入力（study_logの読書版。想起本文は必須、現在ページは任意。要件定義書R-65）。

    ページの入力欄は現在ページ1つだけとする（仕様変更2026-09-11）。「読んだページ数」は
    利用者が毎日覚えていられない値であるうえ、読書は定量的な進捗管理を行わない目標
    （R-71）であり保持する意味を持たないため廃止した。現在ページの上限は書籍の総ページ数
    であり、その検証は書籍を参照できるサービス層（record_service）で行う。
    """

    book_id: int
    recall_body: str = Field(min_length=1)
    #: 時間枠ごとの読書時間（任意）。読書もリソース配分の対象（R-64）だが、
    #: 記録した時間は速度算出には用いない（R-71）。
    slot_minutes: list[SlotMinutesInput] = Field(default_factory=list)
    current_page: int | None = Field(default=None, ge=0)


class ReadingLogRead(BaseModel):
    id: int
    book_id: int
    recall_body: str
    minutes_spent: int | None
    slot_minutes: list[SlotMinutesRead]
    current_page: int | None


class WorkLogInput(BaseModel):
    """業務記録の入力（study_logの仕事版。自由記述本文のみ、数値実績は必須としない。
    要件定義書R-75）。"""

    work_assignment_id: int
    body: str = Field(min_length=1)


class WorkLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_assignment_id: int
    body: str


class DiaryEntryInput(BaseModel):
    """日記（目標別）の登録入力。本文・学んだこと両方が空の目標は送信対象から除外する
    （フロントエンドのbuildDiaryEntriesPayloadと同じ考え方、StudyLogInputと同じ配列パターン）。
    """

    goal_id: int
    diary_body: str = ""
    diary_learned: str = ""


class DiaryEntryRead(BaseModel):
    goal_id: int | None
    goal_name: str | None
    diary_body: str | None
    diary_learned: str | None


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1)


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    body: str
    created_at: dt.datetime
    updated_at: dt.datetime


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int | None
    purpose: AiPurpose
    role: ChatRole
    content: str
    sequence: int
    created_at: dt.datetime


class DailyRecordRead(BaseModel):
    """確定状態（*_record_state/*_reported_at）はカテゴリ（EXAM/READING/WORK）ごとに
    独立して持つ（仕様変更2026-09-05: 資格勉強を確定しても読書・仕事は引き続き入力・
    確定できるようにするため）。値がNoneのカテゴリは、その日一度もそのカテゴリを
    操作していないことを表す。
    """

    record_date: dt.date
    exam_record_state: RecordState | None
    exam_reported_at: dt.datetime | None
    reading_record_state: RecordState | None
    reading_reported_at: dt.datetime | None
    work_record_state: RecordState | None
    work_reported_at: dt.datetime | None
    diary_entries: list[DiaryEntryRead]
    study_logs: list[StudyLogRead]
    reading_logs: list[ReadingLogRead]
    work_logs: list[WorkLogRead]
    comments: list[CommentRead]
    chat_messages: list[ChatMessageRead]


class ProgressRegisterRequest(BaseModel):
    """study_logs・reading_logs・work_logsのいずれかを1件以上含むことをrecord_serviceで
    検証する（すべて空の入力を拒否。複数カテゴリの目標が同時進行しうるため、schema側では
    特定の1つのみのmin_length指定はできない）。"""

    study_logs: list[StudyLogInput] = Field(default_factory=list)
    reading_logs: list[ReadingLogInput] = Field(default_factory=list)
    work_logs: list[WorkLogInput] = Field(default_factory=list)


class FinalizeRequest(BaseModel):
    """資格勉強（EXAM）の報告確定リクエスト（データ構造編6.2 POST /records/{date}/finalize）。
    読書・仕事は別エンドポイント（ReadingFinalizeRequest/WorkFinalizeRequest）に分離した
    （仕様変更2026-09-05: カテゴリごとに独立して確定できるようにするため）。
    """

    study_logs: list[StudyLogInput] = Field(default_factory=list)
    diary_entries: list[DiaryEntryInput] = Field(default_factory=list)


class ReadingFinalizeRequest(BaseModel):
    """読書の報告確定リクエスト（データ構造編6.2 POST /records/{date}/reading-finalize）。
    ChatRequest/ReadingChatRequestと同じ設計方針でカテゴリ別に分離する。
    """

    reading_logs: list[ReadingLogInput] = Field(default_factory=list)


class WorkFinalizeRequest(BaseModel):
    """仕事の報告確定リクエスト（データ構造編6.2 POST /records/{date}/work-finalize）。
    ChatRequest/WorkChatRequestと同じ設計方針でカテゴリ別に分離する。
    """

    work_logs: list[WorkLogInput] = Field(default_factory=list)


class TodayRead(BaseModel):
    logical_date: dt.date
    record_state: RecordState | None


class QuotaItemRead(BaseModel):
    """日次記録画面（SC-06/SC-07）の実績入力行に必要な教材情報（仕様書6.5）。

    unit_label・quality_metric_type は、投下量の単位表示と品質指標の入力形式切替
    （客観正答率/自己採点得点率＝0〜100の数値、主観的手応え＝5段階選択、NONE＝入力欄なし）
    をフロントエンド側で判定するために含める（14.1、技術選定書4.5「品質指標の入力形式切替」）。
    """

    material_id: int
    material_name: str
    unit_label: str
    current_cycle: int
    planned_cycles: int
    daily_quota: float
    quality_metric_type: QualityMetricType
    goal_id: int
    goal_name: str
    #: 時間枠ごとの投下時間入力欄の既定値（配分済みの枠のみ。仕様書6.5「初期値」）。
    slot_defaults: list[SlotDefaultMinutesRead]


class ChatRequest(BaseModel):
    """AI対話の実行（1往復）リクエスト（データ構造編6.2 POST /records/{date}/chat）。

    study_logs・diary_entries はこの時点でDBへ確定させない下書き値であり、
    プロンプト組み立てにのみ使用する（AI呼び出し失敗時も入力を失わないため、16.7）。
    message は2往復目以降の自由入力。1往復目（本日最初の呼び出し）は省略できる。
    goal_id は対象目標（GoalTabBarで選択中の1件）。Phase26で日次フィードバックを
    目標単位の会話へ分離したことに伴い必須化した。
    """

    goal_id: int
    message: str | None = Field(default=None, min_length=1)
    study_logs: list[StudyLogInput] = Field(default_factory=list)
    diary_entries: list[DiaryEntryInput] = Field(default_factory=list)


class ChatResponse(BaseModel):
    record: DailyRecordRead
    assistant_message: ChatMessageRead
    was_truncated: bool


class ReadingChatRequest(BaseModel):
    """読書目標のAI対話の実行（1往復）リクエスト（データ構造編6.2
    POST /records/{date}/reading-chat）。ChatRequestと同じ設計：reading_logsはこの時点で
    DBへ確定させない下書き値であり、プロンプト組み立てにのみ使用する。goal_idはChatRequestと
    同じ理由でPhase26にて必須化した。
    """

    goal_id: int
    message: str | None = Field(default=None, min_length=1)
    reading_logs: list[ReadingLogInput] = Field(default_factory=list)


class WorkChatRequest(BaseModel):
    """仕事目標のAI対話の実行（1往復）リクエスト（データ構造編6.2
    POST /records/{date}/work-chat）。ChatRequest・ReadingChatRequestと同じ設計：
    work_logsはこの時点でDBへ確定させない下書き値であり、プロンプト組み立てにのみ使用する。
    goal_idはChatRequestと同じ理由でPhase26にて必須化した。
    """

    goal_id: int
    message: str | None = Field(default=None, min_length=1)
    work_logs: list[WorkLogInput] = Field(default_factory=list)


class DailyMessageRead(BaseModel):
    target_date: dt.date
    goal_id: int | None
    goal_name: str | None
    body: str
    generated_at: dt.datetime
