"""計画基準値の記録と取得（設計書 ロジック・プロンプト編 12章）。

reason は呼び出し側（Phase3以降のAPI層）が契機（INITIAL / REPLAN / EXAM_DATE_FIXED /
MATERIAL_CHANGED / CYCLE_CHANGED）に応じて指定する。本サービスは記録・取得のみを担う。
"""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

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


@dataclass(frozen=True)
class BaselineChange:
    """リプラン履歴の1件（変更前後のノルマを含む、仕様書6.10・設計書ロジック・プロンプト編17.5
    `{{replan_history}}`、データ構造編7.1 `replan_history`）。quota_beforeは同一教材の直前の
    基準値（INITIALのみNone）。"""

    material_id: int
    effective_from: dt.date
    reason: BaselineReason
    quota_before: float | None
    quota_after: float
    remaining_at_baseline: float
    plan_days_at_baseline: int


def compute_baseline_changes(baselines: list[PlanBaseline]) -> list[BaselineChange]:
    """PlanBaseline列から、教材ごとに直前の基準値との差分(quota_before→quota_after)を算出する
    （goal_service.get_baselinesの出力のように複数教材が混在するリストを渡してよい）。
    総括レポート・ナレッジエクスポートの双方で使う共通処理（CLAUDE.md DRYの原則）。
    """
    by_material: dict[int, list[PlanBaseline]] = defaultdict(list)
    for baseline in baselines:
        by_material[baseline.material_id].append(baseline)

    changes: list[BaselineChange] = []
    for material_baselines in by_material.values():
        ordered = sorted(material_baselines, key=lambda b: (b.effective_from, b.id))
        previous_quota: float | None = None
        for baseline in ordered:
            changes.append(
                BaselineChange(
                    material_id=baseline.material_id,
                    effective_from=baseline.effective_from,
                    reason=baseline.reason,
                    quota_before=previous_quota,
                    quota_after=baseline.baseline_daily_quota,
                    remaining_at_baseline=baseline.remaining_at_baseline,
                    plan_days_at_baseline=baseline.plan_days_at_baseline,
                )
            )
            previous_quota = baseline.baseline_daily_quota

    changes.sort(key=lambda c: (c.effective_from, c.material_id), reverse=True)
    return changes
