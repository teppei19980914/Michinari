"""AIによるスケジュール修正案のリクエスト/レスポンススキーマ
（開発Todo_スケジュール・ガントチャート_v1.1 第13章・13.7、単位5）。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, model_validator

from app.constants.enums import (
    ScheduleItemStatus,
    ScheduleRevisionDecision,
    ScheduleRevisionItemKind,
    ScheduleRevisionProposalStatus,
    ScheduleRevisionTrigger,
)


class ScheduleRevisionGenerateRequest(BaseModel):
    """`POST /goals/{goal_id}/schedule/revision-proposals` のリクエスト（13.7）。

    AUTOの場合は`record_date`（自動生成のきっかけとなった報告対象日）を必須とする
    （13.2の1日1回の判定に使う）。MANUALでは使わないため常にNone。
    """

    trigger: ScheduleRevisionTrigger
    record_date: dt.date | None = None

    @model_validator(mode="after")
    def _check_record_date_required_for_auto(self) -> ScheduleRevisionGenerateRequest:
        if self.trigger == ScheduleRevisionTrigger.AUTO and self.record_date is None:
            raise ValueError("record_date is required when trigger is AUTO")
        return self


class ScheduleRevisionProposalItemRead(BaseModel):
    """修正案の行（本書13.6）。"""

    id: int
    schedule_item_id: int
    kind: ScheduleRevisionItemKind
    before_planned_start_date: dt.date
    before_planned_end_date: dt.date
    before_status: ScheduleItemStatus
    proposed_planned_start_date: dt.date | None
    proposed_planned_end_date: dt.date | None
    reason: str
    decision: ScheduleRevisionDecision
    applied_planned_start_date: dt.date | None
    applied_planned_end_date: dt.date | None
    reject_reason: str | None
    #: 変更前の値（before_*）が現在のschedule_itemの値と一致しないかどうか（D-59）。
    #: 一致しない行は画面側で承認・却下のボタンを押せないようにする（13.8）。
    is_stale: bool


class ScheduleRevisionProposalRead(BaseModel):
    """修正案1件（本書13.6）。`GET /goals/{goal_id}/schedule`が未判断の修正案として
    埋め込む形・生成API・判断APIの応答のいずれも、本スキーマで統一する。
    """

    id: int
    goal_id: int
    trigger: ScheduleRevisionTrigger
    record_date: dt.date | None
    summary: str | None
    status: ScheduleRevisionProposalStatus
    items: list[ScheduleRevisionProposalItemRead]


class ScheduleRevisionGenerateResult(BaseModel):
    """生成APIの応答（13.7）。有効な変更・注意のいずれも無い場合、またはAUTOで対象の遅れが
    無い場合は`proposal`をNoneとする（「対象なし」「修正が必要な行はありませんでした」）。
    """

    proposal: ScheduleRevisionProposalRead | None


class ScheduleRevisionDecisionInput(BaseModel):
    """判断1件分（本書13.7）。CHANGE行はAPPROVED/REJECTED、WARNING行はACKNOWLEDGEDのみ
    受け付ける（組み合わせの検証はサービス層、本書6.1と同じ方針）。
    """

    proposal_item_id: int
    decision: ScheduleRevisionDecision
    #: 承認時に利用者が日付を修正した場合の値（本書13.8「日付は修正可」）。
    #: 指定しない場合はAIが提案した日付（proposed_*）のまま承認する。
    planned_start_date: dt.date | None = None
    planned_end_date: dt.date | None = None
    #: 却下の理由（任意、D-56）。
    reject_reason: str | None = None


class ScheduleRevisionDecisionsRequest(BaseModel):
    decisions: list[ScheduleRevisionDecisionInput]


class ScheduleRevisionDecisionOutcome(BaseModel):
    """判断1件分の処理結果（単位5開発Todo2章補足6）。

    変更前の値が現在の値と一致せず適用できなかった行は`applied=False`・
    `blocked_reason="STALE_BEFORE_VALUE"`とし、他の行の処理は継続する（本書13.7）。
    新しい予定日が13.5の制約に反する行（翌日以降に承認した場合等）も同様に
    `applied=False`・`blocked_reason="INVALID_PLANNED_DATE"`とし、他の行の処理へ
    影響させない（開発Todo_スケジュール・ガントチャート_検証修正_v1.0.md 修正1）。
    """

    proposal_item_id: int
    applied: bool
    blocked_reason: str | None = None


class ScheduleRevisionDecisionsResponse(BaseModel):
    proposal: ScheduleRevisionProposalRead
    outcomes: list[ScheduleRevisionDecisionOutcome]
