"""節目のお祝い（開発Todo_節目のお祝い_v1.0）：資格試験（category=EXAM）固有の判定。

教材1周完了（閾値を持たないイベント型、周回ごとに1件）と、目標全体の進捗率(%)の節目を
判定する。連続/累計記録日数は3種別共通のため`milestone_service_common.py`が判定する。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import MILESTONE_EXAM_OVERALL_PROGRESS_THRESHOLDS
from app.constants.enums import MilestoneType
from app.models.goal import Goal
from app.services import cycle_service, material_service, metrics_service, setting_reader
from app.services.milestone_service_common import PendingMilestone


def detect_exam_milestones(session: Session, goal: Goal, today: dt.date) -> list[PendingMilestone]:
    materials = material_service.list_active_materials(goal)
    if not materials:
        return []

    pending: list[PendingMilestone] = []
    progresses = {m.id: cycle_service.get_material_progress(session, m) for m in materials}

    for material in materials:
        progress = progresses[material.id]
        completed_cycles = cycle_service.compute_completed_cycles(material, progress)
        for cycle_number in range(1, completed_cycles + 1):
            pending.append(
                PendingMilestone(
                    MilestoneType.EXAM_MATERIAL_CYCLE_COMPLETED,
                    f"{material.id}:{cycle_number}",
                )
            )

    overall_progress_rate = metrics_service.compute_goal_overall_progress_rate(
        materials, progresses
    )
    if overall_progress_rate is not None:
        overall_progress_percent = overall_progress_rate * 100
        thresholds = setting_reader.get_int_list(
            session, MILESTONE_EXAM_OVERALL_PROGRESS_THRESHOLDS
        )
        for threshold in thresholds:
            if overall_progress_percent >= threshold:
                pending.append(
                    PendingMilestone(MilestoneType.EXAM_OVERALL_PROGRESS, str(threshold))
                )

    return pending
