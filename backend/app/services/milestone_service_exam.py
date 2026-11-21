"""節目のお祝い（開発Todo_節目のお祝い_v1.0）：資格試験（category=EXAM）固有の判定。

教材1周完了（閾値を持たないイベント型、周回ごとに1件）・目標全体の進捗率(%)・単語帳の
習得用語数（開発Todo_単語帳_v1.0 要件E E-U2）の節目を判定する。連続/累計記録日数は
3種別共通のため`milestone_service_common.py`が判定する。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import (
    MILESTONE_EXAM_OVERALL_PROGRESS_THRESHOLDS,
    MILESTONE_VOCAB_MASTERED_TERMS_THRESHOLDS,
    VOCAB_MASTERY_STREAK,
)
from app.constants.enums import MilestoneType
from app.models.goal import Goal
from app.services import (
    cycle_service,
    material_service,
    metrics_service,
    setting_reader,
    vocab_service,
)
from app.services.milestone_service_common import PendingMilestone, threshold_milestones


def _detect_vocab_mastery_milestones(session: Session, goal: Goal) -> list[PendingMilestone]:
    """単語帳の習得用語数（その目標のすべての単語帳の合計）の節目を判定する
    （開発Todo_単語帳_v1.0 要件E E-U1・E-U2）。単語帳が1つも無い目標は何も返さない
    （`compute_goal_vocab_mastery`がtotal_cards=0を返し、閾値判定が自然に空になる）。
    """
    mastery_streak = setting_reader.get_int(session, VOCAB_MASTERY_STREAK)
    totals = vocab_service.compute_goal_vocab_mastery(session, goal.id, mastery_streak)
    return threshold_milestones(
        session,
        MILESTONE_VOCAB_MASTERED_TERMS_THRESHOLDS,
        totals.mastered_cards,
        MilestoneType.VOCAB_MASTERED_TERMS,
    )


def detect_exam_milestones(session: Session, goal: Goal, today: dt.date) -> list[PendingMilestone]:
    """資格試験目標の節目を判定する。`today`は他種別の判定関数と形を揺らせないための
    引数で、ここでは使わない（教材1周完了・全体進捗率・単語帳の習得用語数はいずれも
    日付に依存しない）。
    """
    pending: list[PendingMilestone] = []
    materials = material_service.list_active_materials(goal)
    if materials:
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

        # materialsが空でないため、必ずfloatが返る（compute_goal_overall_progress_rateが
        # Noneを返すのはmaterialsが空の場合のみ）。
        overall_progress_percent = (
            metrics_service.compute_goal_overall_progress_rate(materials, progresses) * 100
        )
        pending += threshold_milestones(
            session,
            MILESTONE_EXAM_OVERALL_PROGRESS_THRESHOLDS,
            overall_progress_percent,
            MilestoneType.EXAM_OVERALL_PROGRESS,
        )

    pending += _detect_vocab_mastery_milestones(session, goal)
    return pending
