"""資格試験テンプレートのレスポンススキーマ（実装フェーズ分割計画書Phase38）。

テンプレートはDBに保存せず`backend/app/templates/exams/`配下のJSONファイルとして
同梱し、都度読み込む（CLAUDE.md「データベースのスキーマを変更しないこと」）。
フィールド名は`SubjectCreate`（schemas/subject.py）・`MaterialCreate`
（schemas/material.py）と揃え、ウィザードがテンプレートの値をそのままAPIへ
引き渡せるようにしている。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.constants.enums import PassingScoreType


class ExamTemplateSubject(BaseModel):
    name: str = Field(min_length=1)
    passing_score_type: PassingScoreType = PassingScoreType.PERCENTAGE
    passing_score: float = Field(ge=0)


class ExamTemplateMaterial(BaseModel):
    name: str = Field(min_length=1)
    unit_label: str = Field(min_length=1)
    total_amount: float = Field(ge=0)
    planned_cycles: int = Field(default=1, ge=1)
    #: この教材が対策する科目名（ExamTemplateSubject.nameを参照する。IDはウィザード
    #: 実行時に採番されるため、テンプレート内では名前で紐付ける）。
    subject_names: list[str] = Field(min_length=1)


class ExamTemplateRead(BaseModel):
    id: str
    exam_name: str
    subjects: list[ExamTemplateSubject] = Field(min_length=1)
    materials: list[ExamTemplateMaterial] = Field(default_factory=list)
