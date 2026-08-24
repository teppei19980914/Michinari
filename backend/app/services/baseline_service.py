"""計画基準値の記録と取得（設計書 ロジック・プロンプト編 12章）。

reason は呼び出し側（Phase3以降のAPI層）が契機（INITIAL / REPLAN / EXAM_DATE_FIXED /
MATERIAL_CHANGED / CYCLE_CHANGED）に応じて指定する。本サービスは記録・取得のみを担う。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.enums import BaselineReason
from app.models.material import Material, PlanBaseline


def record_baseline(
    session: Session,
    material: Material,
    reason: BaselineReason,
    effective_from: dt.date,
    baseline_daily_quota: float,
    remaining_at_baseline: float,
    plan_days_at_baseline: int,
) -> PlanBaseline:
    """計画基準値を記録する（12.2）。"""
    baseline = PlanBaseline(
        material_id=material.id,
        effective_from=effective_from,
        baseline_daily_quota=baseline_daily_quota,
        remaining_at_baseline=remaining_at_baseline,
        plan_days_at_baseline=plan_days_at_baseline,
        planned_cycles_at_baseline=material.planned_cycles,
        reason=reason,
    )
    session.add(baseline)
    session.flush()
    return baseline


def get_current_baseline(session: Session, material_id: int, today: dt.date) -> PlanBaseline | None:
    """現在有効な基準値を取得する（effective_from が本日以前で最大のもの、12章）。"""
    return (
        session.query(PlanBaseline)
        .filter(PlanBaseline.material_id == material_id, PlanBaseline.effective_from <= today)
        .order_by(PlanBaseline.effective_from.desc(), PlanBaseline.id.desc())
        .first()
    )
