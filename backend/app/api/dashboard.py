"""ダッシュボードのAPI（仕様書6.1 SC-01、実装フェーズ分割計画書Phase6）。

Phase2〜5で実装・テスト済みのサービス（cycle_service・quota_service・speed_service・
threshold_service・metrics_service・slot_service・calendar_service・material_service）を
呼び出して組み立てるだけの薄い層。新たな業務ロジックはここに書かない（データ構造編8.1
「api層: 業務ロジックの記述」禁止）。

目標単位の集計値（全体進捗率・完了予測日との乖離）は、ロジック・プロンプト編13.2が
定める「教材ごとの値の平均を目標単位の参考値として表示する」という考え方を、
完了予測日の乖離にも同様に適用したもの（教材ごとの単位・締切が異なり単純合算できない
ため）。残日数は目標配下の試験科目のうち最も近い受験日までの日数とする。
"""

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.books import serialize_book
from app.constants.app_setting_keys import DASHBOARD_REPORT_RATE_WINDOW_DAYS
from app.constants.enums import GoalCategory
from app.database import get_db
from app.models.goal import Goal
from app.models.material import Material
from app.schemas.dashboard import (
    DashboardRead,
    GoalCardRead,
    GoalStatsRead,
    MaterialSpeedRead,
    TodayQuotaEntryRead,
)
from app.services import (
    ai_context_service,
    calendar_service,
    cycle_service,
    goal_service,
    material_service,
    metrics_service,
    quota_service,
    record_service,
    setting_reader,
    slot_service,
    speed_service,
    threshold_service,
)
from app.services.speed_service import EffectiveSpeed

router = APIRouter(tags=["dashboard"])


def _goal_remaining_days(goal: Goal, today: dt.date) -> int | None:
    if not goal.exam_subjects:
        return None
    nearest = min(material_service.effective_exam_date(s) for s in goal.exam_subjects)
    return (nearest - today).days


def _build_goal_card_and_stats(
    session: Session,
    goal: Goal,
    materials: list[Material],
    today: dt.date,
    today_day_type,
    treat_holiday_as_buffer: bool,
    report_rate_window_days: int,
    effective_speed_by_material: dict[int, EffectiveSpeed | None],
) -> tuple[GoalCardRead, GoalStatsRead]:
    """1目標分の目標カード・統計サマリを組み立てる（材料ごとの計算を1回ずつ行い使い回す、
    CLAUDE.md パフォーマンスチェック: N+1禁止）。
    """
    progresses = {m.id: cycle_service.get_material_progress(session, m) for m in materials}
    quotas = {
        m.id: quota_service.compute_material_quota(session, goal, m, today, treat_holiday_as_buffer)
        for m in materials
    }
    forecasts = {
        m.id: speed_service.compute_forecast_date(
            session, goal, m, materials, today, treat_holiday_as_buffer
        )
        for m in materials
    }
    for material in materials:
        effective_speed_by_material[material.id] = speed_service.compute_effective_speed(
            session, material, progresses[material.id].current_cycle
        )

    progress_rate = (
        sum(metrics_service.compute_progress_rate(progresses[m.id]) for m in materials)
        / len(materials)
        if materials
        else None
    )
    deviations = [
        forecast.overrun_days
        for forecast in forecasts.values()
        if forecast.overrun_days is not None
    ]
    forecast_deviation_days = sum(deviations) / len(deviations) if deviations else None

    has_warning = any(
        threshold_service.check_warning(session, m.id, today, today_day_type, quotas[m.id])
        for m in materials
    )
    has_forced_replan = any(
        threshold_service.check_forced_replan(session, forecasts[m.id].overrun_days)
        for m in materials
    )

    card = GoalCardRead(
        goal_id=goal.id,
        goal_name=goal.name,
        category=goal.category,
        progress_rate=progress_rate,
        remaining_days=_goal_remaining_days(goal, today),
        forecast_deviation_days=forecast_deviation_days,
        has_warning=has_warning,
        has_forced_replan=has_forced_replan,
    )

    material_speeds = [
        MaterialSpeedRead(
            material_id=material.id,
            material_name=material.name,
            unit_label=material.unit_label,
            speed=(
                effective_speed_by_material[material.id].speed
                if effective_speed_by_material[material.id] is not None
                else None
            ),
        )
        for material in materials
    ]
    stats = GoalStatsRead(
        goal_id=goal.id,
        goal_name=goal.name,
        consecutive_report_days=metrics_service.compute_consecutive_report_days(
            session, goal, today, treat_holiday_as_buffer
        ),
        recent_report_rate=metrics_service.compute_recent_report_rate(
            session, goal, today, report_rate_window_days
        ),
        buffer_usage_rate=metrics_service.compute_buffer_usage_rate(
            session, goal, today, treat_holiday_as_buffer
        ),
        material_speeds=material_speeds,
    )
    return card, stats


def _build_today_quota(
    session: Session,
    today: dt.date,
    materials_by_id: dict[int, Material],
    effective_speed_by_material: dict[int, EffectiveSpeed | None],
) -> list[TodayQuotaEntryRead]:
    """材料情報はmaterials_by_id（呼び出し側で目標一覧を辿る際に一括収集済み）から引く。
    1件ずつDBへ問い合わせない（CLAUDE.md パフォーマンスチェック: N+1禁止）。
    """
    entries = []
    for item in record_service.compute_daily_quota(session, today):
        material = materials_by_id[item.material_id]
        effective_speed = effective_speed_by_material.get(item.material_id)
        target_minutes = (
            item.daily_quota / effective_speed.speed * 60
            if effective_speed is not None and effective_speed.speed > 0
            else None
        )
        entries.append(
            TodayQuotaEntryRead(
                material_id=item.material_id,
                material_name=item.material_name,
                current_cycle=item.current_cycle,
                planned_cycles=item.planned_cycles,
                daily_quota=item.daily_quota,
                unit_label=material.unit_label,
                target_minutes=target_minutes,
                goal_id=item.goal_id,
                goal_name=item.goal_name,
            )
        )
    return entries


@router.get("/dashboard", response_model=DashboardRead)
def get_dashboard(session: Session = Depends(get_db)) -> DashboardRead:
    today = goal_service.resolve_today(session)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    today_day_type = calendar_service.resolve_day_type(session, today, treat_holiday_as_buffer)
    report_rate_window_days = setting_reader.get_int(session, DASHBOARD_REPORT_RATE_WINDOW_DAYS)
    today_record = record_service.get_daily_record(session, today)

    active_goals = ai_context_service.list_active_goals(session)
    effective_speed_by_material: dict[int, EffectiveSpeed | None] = {}
    materials_by_id: dict[int, Material] = {}

    goal_cards: list[GoalCardRead] = []
    goal_stats: list[GoalStatsRead] = []
    for goal in active_goals:
        materials = material_service.list_active_materials(goal)
        materials_by_id.update({m.id: m for m in materials})
        card, stats = _build_goal_card_and_stats(
            session,
            goal,
            materials,
            today,
            today_day_type,
            treat_holiday_as_buffer,
            report_rate_window_days,
            effective_speed_by_material,
        )
        if goal.category == GoalCategory.READING and goal.book is not None:
            # 読書目標は残日数・ページ進捗（任意）を書籍の派生値で表示する（要件定義書R-66）。
            # 完了予測日との乖離・警告・強制リプランは対象外（EXAM専用の計画管理のため）。
            book_read = serialize_book(session, goal.book)
            card = card.model_copy(
                update={
                    "progress_rate": book_read.progress_rate,
                    "remaining_days": book_read.remaining_days,
                    "book": book_read,
                }
            )
        goal_cards.append(card)
        goal_stats.append(stats)

    today_quota = _build_today_quota(session, today, materials_by_id, effective_speed_by_material)

    slots_by_weekday = slot_service.group_slots_by_weekday(slot_service.get_active_slots(session))
    available_slot_names = [slot.name for slot in slots_by_weekday.get(today.weekday(), [])]

    return DashboardRead(
        logical_date=today,
        record_state=today_record.record_state if today_record else None,
        today_day_type=today_day_type,
        report_rate_window_days=report_rate_window_days,
        goal_cards=goal_cards,
        goal_stats=goal_stats,
        today_quota=today_quota,
        available_slot_names=available_slot_names,
    )
