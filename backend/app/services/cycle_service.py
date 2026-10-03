"""周回の導出（設計書 ロジック・プロンプト編 6章）。

総作業量・残量・現在周回はいずれもDBに保存しない派生値であり、都度算出する（CLAUDE.md）。
"""

import datetime as dt
import math
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.record import DailyRecord, StudyLog
from app.services.exceptions import PlannedCyclesBelowCompletedError


@dataclass(frozen=True)
class MaterialProgress:
    """教材の進捗算出結果（6.1、6.2）。"""

    total_work: float
    completed: float
    remaining: float
    current_cycle: int


@dataclass(frozen=True)
class CurrentCycleProgress:
    """現在周回内の進捗（6.2）。"""

    completed_in_cycle: float
    progress_rate_in_cycle: float


def get_completed_amount(session: Session, material_id: int) -> float:
    """教材の累積完了量 C(m)（全周回合計）を集計する（6.1）。"""
    total = (
        session.query(func.sum(StudyLog.amount_completed))
        .filter(StudyLog.material_id == material_id)
        .scalar()
    )
    return float(total) if total is not None else 0.0


def compute_progress(material: Material, completed: float) -> MaterialProgress:
    """完了量からTW(m)・R(m)・k(m)を算出する（6.1）。"""
    total_work = material.total_amount * material.planned_cycles
    remaining = max(0.0, total_work - completed)

    if completed >= total_work:
        current_cycle = material.planned_cycles
    else:
        current_cycle = min(
            material.planned_cycles, math.floor(completed / material.total_amount) + 1
        )

    return MaterialProgress(
        total_work=total_work,
        completed=completed,
        remaining=remaining,
        current_cycle=current_cycle,
    )


def get_material_progress(session: Session, material: Material) -> MaterialProgress:
    """教材の進捗を取得する（DB集計 + 算出）。"""
    completed = get_completed_amount(session, material.id)
    return compute_progress(material, completed)


def compute_current_cycle_progress(
    material: Material, progress: MaterialProgress
) -> CurrentCycleProgress:
    """現在周回内の完了量・進捗率を算出する（6.2）。"""
    completed_in_cycle = progress.completed - material.total_amount * (progress.current_cycle - 1)
    progress_rate_in_cycle = (
        completed_in_cycle / material.total_amount if material.total_amount > 0 else 0.0
    )
    return CurrentCycleProgress(
        completed_in_cycle=completed_in_cycle,
        progress_rate_in_cycle=progress_rate_in_cycle,
    )


@dataclass(frozen=True)
class ProgressPoint:
    """累積完了量の1点（分析画面ANL-向け、6.1のC(m)を日付付きで返したもの）。"""

    record_date: dt.date
    cumulative_completed: float


@dataclass(frozen=True)
class CycleBoundary:
    """周回の区切り（分析画面「累積完了量と計画線の比較。周回の区切りを表示」）。"""

    cycle_number: int
    record_date: dt.date


def compute_cumulative_progress(session: Session, material_id: int) -> list[ProgressPoint]:
    """日付順に累積完了量C(m)を積み上げる（6.1、分析画面「進捗」タブの実績系列）。"""
    rows = (
        session.query(DailyRecord.record_date, func.sum(StudyLog.amount_completed))
        .join(StudyLog, StudyLog.daily_record_id == DailyRecord.id)
        .filter(StudyLog.material_id == material_id)
        .group_by(DailyRecord.record_date)
        .order_by(DailyRecord.record_date)
        .all()
    )
    points: list[ProgressPoint] = []
    running_total = 0.0
    for record_date, day_amount in rows:
        running_total += day_amount
        points.append(ProgressPoint(record_date=record_date, cumulative_completed=running_total))
    return points


def compute_cycle_boundaries(
    material: Material, points: list[ProgressPoint]
) -> list[CycleBoundary]:
    """実績の累積が周回境界（total_amountの倍数）を越えた日付を特定する。

    予定周回数-1件目まで（最終周回の到達は「完了」であり区切り線の対象ではない）。
    まだ到達していない周回境界は含めない。
    """
    boundaries: list[CycleBoundary] = []
    for cycle_number in range(1, material.planned_cycles):
        threshold = material.total_amount * cycle_number
        crossing = next((p for p in points if p.cumulative_completed >= threshold), None)
        if crossing is not None:
            boundaries.append(
                CycleBoundary(cycle_number=cycle_number, record_date=crossing.record_date)
            )
    return boundaries


def compute_completed_cycles(material: Material, progress: MaterialProgress) -> int:
    """完了済み周回数を算出する（総括レポート・ナレッジエクスポート向け、6.1のcurrent_cycleとは
    異なり「完了した」周回のみを数える。current_cycleは実行中の周回を含むため、
    total_amountの倍数に達した回数で別途算出する）。"""
    if material.total_amount <= 0:
        return 0
    return min(material.planned_cycles, math.floor(progress.completed / material.total_amount))


def validate_planned_cycles_change(current_cycle: int, new_planned_cycles: int) -> None:
    """予定周回数の変更可否を検証する（6.4）。

    完了済み周回数（現在周回）を下回る変更は拒否する。DBの更新自体はAPI層（Phase3）が行う。
    """
    if new_planned_cycles < current_cycle:
        raise PlannedCyclesBelowCompletedError(current_cycle, new_planned_cycles)
