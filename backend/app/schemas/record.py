"""日次記録のリクエスト/レスポンススキーマ（データ構造編5.4・6.2、仕様書6.4〜6.7・14章）。

品質指標（quality_value）は教材の quality_metric_type に応じて入力形式が異なる
（SUBJECTIVEは1〜5、それ以外は0〜100）ため、正規化はサービス層（record_service）で行う。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.constants.enums import ChatRole, QualityMetricType, RecordState


class StudyLogInput(BaseModel):
    material_id: int
    minutes_spent: int | None = Field(default=None, ge=0)
    amount_completed: float = Field(ge=0)
    cycle_number: int | None = Field(default=None, ge=1)
    quality_value: float | None = None


class StudyLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    minutes_spent: int | None
    amount_completed: float
    cycle_number: int
    quality_value: float | None


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
    role: ChatRole
    content: str
    sequence: int
    created_at: dt.datetime


class DailyRecordRead(BaseModel):
    record_date: dt.date
    record_state: RecordState | None
    diary_entries: list[DiaryEntryRead]
    reported_at: dt.datetime | None
    study_logs: list[StudyLogRead]
    comments: list[CommentRead]
    chat_messages: list[ChatMessageRead]


class ProgressRegisterRequest(BaseModel):
    study_logs: list[StudyLogInput] = Field(min_length=1)


class FinalizeRequest(BaseModel):
    study_logs: list[StudyLogInput] = Field(default_factory=list)
    diary_entries: list[DiaryEntryInput] = Field(default_factory=list)


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


class ChatRequest(BaseModel):
    """AI対話の実行（1往復）リクエスト（データ構造編6.2 POST /records/{date}/chat）。

    study_logs・diary_entries はこの時点でDBへ確定させない下書き値であり、
    プロンプト組み立てにのみ使用する（AI呼び出し失敗時も入力を失わないため、16.7）。
    message は2往復目以降の自由入力。1往復目（本日最初の呼び出し）は省略できる。
    """

    message: str | None = Field(default=None, min_length=1)
    study_logs: list[StudyLogInput] = Field(default_factory=list)
    diary_entries: list[DiaryEntryInput] = Field(default_factory=list)


class ChatResponse(BaseModel):
    record: DailyRecordRead
    assistant_message: ChatMessageRead
    was_truncated: bool


class DailyMessageRead(BaseModel):
    target_date: dt.date
    goal_id: int | None
    goal_name: str | None
    body: str
    generated_at: dt.datetime
