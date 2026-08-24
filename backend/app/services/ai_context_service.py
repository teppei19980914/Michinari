"""AIプロンプトへ注入する変数の組み立て（設計書 ロジック・プロンプト編17.2〜17.4）。

どの値をプロンプトへ渡すかは業務判断であり、ai/パッケージの責務外（データ構造編8.1
「ai: 禁止事項=業務判断」）のためservices層に置く。既存のPhase2〜4サービス
（goal_service・cycle_service・quota_service・speed_service・slot_service・
metrics_service・material_service）を組み合わせるのみで、算出ロジック自体は再実装しない
（CLAUDE.md DRYの原則）。
"""

import datetime as dt
from collections import defaultdict

from sqlalchemy.orm import Session

from app.ai.prompt_builder import MaterialStatusEntry
from app.constants.enums import DayType, GoalStatus, RecordState
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, StudyLog, WeeklySummary
from app.services import (
    calendar_service,
    cycle_service,
    material_service,
    metrics_service,
    quota_service,
    speed_service,
)
from app.services import slot_service as slot_service_module
from app.services.record_service import StudyLogItem


def list_active_goals(session: Session) -> list[Goal]:
    """進行中（ACTIVE）の目標一覧を取得する。"""
    return session.query(Goal).filter(Goal.status == GoalStatus.ACTIVE).order_by(Goal.id).all()


def list_active_materials(goals: list[Goal]) -> list[Material]:
    """指定した目標群に属する有効な教材一覧を取得する。"""
    return [material for goal in goals for material in goal.materials if material.is_active]


def _group_materials_by_goal(materials: list[Material]) -> dict[int, list[Material]]:
    """教材を所属goal_idごとにグルーピングする（build_material_status_entries・
    build_slot_summaryで共通利用、DRYの原則）。"""
    by_goal: dict[int, list[Material]] = defaultdict(list)
    for material in materials:
        by_goal[material.goal_id].append(material)
    return by_goal


def _format_days_remaining(today: dt.date, target: dt.date) -> str:
    days = (target - today).days
    if days >= 0:
        return f"残り{days}日"
    return f"{-days}日超過"


def build_goal_summary(goals: list[Goal], today: dt.date) -> str:
    """{{goal_summary}}: 目標名、科目構成、各科目の受験日、残日数（17.2）。"""
    if not goals:
        return "（進行中の目標はありません）"
    lines: list[str] = []
    for goal in goals:
        lines.append(f"■ {goal.name}")
        subjects = sorted(goal.exam_subjects, key=lambda s: s.display_order)
        if not subjects:
            lines.append("  （試験科目未登録）")
            continue
        for subject in subjects:
            exam_date = material_service.effective_exam_date(subject)
            lines.append(
                f"  ・{subject.name}：受験日 {exam_date.isoformat()}"
                f"（{_format_days_remaining(today, exam_date)}）"
            )
    return "\n".join(lines)


def build_material_status_entries(
    session: Session,
    materials: list[Material],
    today: dt.date,
    treat_holiday_as_buffer: bool,
) -> list[MaterialStatusEntry]:
    """{{material_status}}: 教材ごとの総量・予定周回・現在周回・残量・締切・日次ノルマ・
    必要速度・実効速度・完了予測日・乖離日数（17.2）。
    """
    by_goal = _group_materials_by_goal(materials)

    entries: list[MaterialStatusEntry] = []
    for goal_materials in by_goal.values():
        goal = goal_materials[0].goal
        contention = [m for m in goal.materials if m.is_active]
        for material in goal_materials:
            progress = cycle_service.get_material_progress(session, material)
            quota = quota_service.compute_material_quota(
                session, goal, material, today, treat_holiday_as_buffer
            )
            required_speed = speed_service.compute_required_speed(
                session, goal, material, contention, today, treat_holiday_as_buffer
            )
            effective_speed = speed_service.compute_effective_speed(
                session, material, progress.current_cycle
            )
            forecast = speed_service.compute_forecast_date(
                session, goal, material, contention, today, treat_holiday_as_buffer
            )
            required_speed_text = (
                f"{required_speed:.2f}{material.unit_label}/時間"
                if required_speed is not None
                else "算出不可"
            )
            effective_speed_text = (
                f"{effective_speed.speed:.2f}{material.unit_label}/時間"
                if effective_speed is not None
                else "算出不可"
            )
            if forecast.forecast_date is not None:
                # ForecastResultはforecast_dateとoverrun_daysを常にセットで設定する
                # （speed_service.compute_forecast_date）ため、ここでoverrun_daysの
                # None判定は不要。
                forecast_text = (
                    f"完了予測日 {forecast.forecast_date.isoformat()}"
                    f"（乖離 {forecast.overrun_days}日）"
                )
            else:
                forecast_text = "完了予測日 算出不可"
            text = (
                f"■ {material.name}（{goal.name}）\n"
                f"  総量 {material.total_amount}{material.unit_label} ×"
                f" {material.planned_cycles}周、現在{progress.current_cycle}周目、"
                f"残量 {progress.remaining:.1f}{material.unit_label}、"
                f"締切 {material.due_date.isoformat()}\n"
                f"  日次ノルマ {quota:.1f}{material.unit_label}/日、"
                f"必要速度 {required_speed_text}、実効速度 {effective_speed_text}、"
                f"{forecast_text}"
            )
            entries.append(MaterialStatusEntry(due_date=material.due_date, text=text))
    return entries


def build_slot_summary(
    session: Session, materials: list[Material], today: dt.date
) -> str:
    """{{slot_summary}}: 本日利用可能なスロットと教材への割当（17.2）。"""
    slots_by_weekday = slot_service_module.group_slots_by_weekday(
        slot_service_module.get_active_slots(session)
    )
    total_hours = slot_service_module.compute_total_hours_for_date(slots_by_weekday, today)
    if total_hours <= 0:
        return "（本日利用可能なスロットはありません）"

    lines = [f"本日の総利用可能時間: {total_hours:.1f}時間"]
    by_goal = _group_materials_by_goal(materials)

    for goal_materials in by_goal.values():
        goal = goal_materials[0].goal
        weights = speed_service.compute_weights(session, goal_materials)
        allocation = slot_service_module.allocate_day(
            weights, slots_by_weekday, today, goal.resource_ratio
        )
        for material in goal_materials:
            hours = allocation.get(material.id, 0.0)
            if hours > 0:
                lines.append(f"  ・{material.name}: {hours:.2f}時間")
    return "\n".join(lines)


def build_buffer_usage_rate_text(
    session: Session, goals: list[Goal], today: dt.date, treat_holiday_as_buffer: bool
) -> str:
    """{{buffer_usage_rate}}: バッファ日の消費状況（17.2、13.1）。"""
    if not goals:
        return "（進行中の目標はありません）"
    lines = []
    for goal in goals:
        rate = metrics_service.compute_buffer_usage_rate(
            session, goal, today, treat_holiday_as_buffer
        )
        rate_text = f"{rate:.0%}" if rate is not None else "算出不可（経過バッファ日なし）"
        lines.append(f"{goal.name}: {rate_text}")
    return "\n".join(lines)


def build_today_logs_text(items: list[StudyLogItem], materials_by_id: dict[int, Material]) -> str:
    """{{today_logs}}: 本日の教材別実績（投下時間、完了分量、周回、品質指標、17.2）。"""
    if not items:
        return "（本日の実績入力はまだありません）"
    lines = []
    for item in items:
        material = materials_by_id[item.material_id]
        minutes_text = f"{item.minutes_spent}分" if item.minutes_spent else "時間未入力"
        cycle_text = f"{item.cycle_number}周目" if item.cycle_number is not None else "周回未指定"
        quality_text = f"、品質指標 {item.quality_value}" if item.quality_value is not None else ""
        lines.append(
            f"・{material.name}: {item.amount_completed}{material.unit_label}"
            f"（{minutes_text}、{cycle_text}{quality_text}）"
        )
    return "\n".join(lines)


def build_progress_summary(
    session: Session, materials: list[Material]
) -> str:
    """{{progress_summary}}: 教材ごとの進捗率と現在周回（17.4）。"""
    if not materials:
        return "（対象教材はありません）"
    lines = []
    for material in materials:
        progress = cycle_service.get_material_progress(session, material)
        rate = metrics_service.compute_progress_rate(progress)
        lines.append(
            f"・{material.name}: {rate:.0%}（現在{progress.current_cycle}周目）"
        )
    return "\n".join(lines)


def build_recent_activity_text(
    session: Session, goals: list[Goal], today: dt.date, lookback_days: int = 7
) -> str:
    """{{recent_activity}}: 直近N日間の報告状況と実績（17.4、既定7日）。"""
    if not goals:
        return "（進行中の目標はありません）"
    period_start = today - dt.timedelta(days=lookback_days - 1)
    records = (
        session.query(DailyRecord)
        .filter(DailyRecord.record_date >= period_start, DailyRecord.record_date <= today)
        .order_by(DailyRecord.record_date)
        .all()
    )
    if not records:
        return "（直近の実績はありません）"
    lines = []
    for record in records:
        state_text = "報告済み" if record.record_state == RecordState.REPORTED else "進捗のみ"
        total_amount = sum(log.amount_completed for log in record.study_logs)
        lines.append(f"・{record.record_date.isoformat()}: {state_text}、完了量計 {total_amount}")
    return "\n".join(lines)


def build_recent_weekly_summaries(
    session: Session, goals: list[Goal], inject_weeks: int
) -> list[str]:
    """{{weekly_summaries}}: 直近の週次要約を新しい順に（17.2、15.3）。"""
    if not goals:
        return []
    goal_names = {goal.id: goal.name for goal in goals}
    rows = (
        session.query(WeeklySummary)
        .filter(WeeklySummary.goal_id.in_(goal_names))
        .order_by(WeeklySummary.week_start_date.desc())
        .limit(inject_weeks)
        .all()
    )
    return [
        f"[{row.week_start_date.isoformat()}〜{row.week_end_date.isoformat()} "
        f"{goal_names[row.goal_id]}]\n{row.summary_body}"
        for row in rows
    ]


def build_week_logs_text(
    session: Session, goal: Goal, week_start: dt.date, week_end: dt.date
) -> str:
    """{{week_logs}}: 週内の日別実績（周回を含む、17.3）。"""
    material_ids = [material.id for material in goal.materials]
    if not material_ids:
        return "（対象教材はありません）"
    rows = (
        session.query(
            DailyRecord.record_date,
            StudyLog.material_id,
            StudyLog.amount_completed,
            StudyLog.cycle_number,
            StudyLog.minutes_spent,
        )
        .join(StudyLog, StudyLog.daily_record_id == DailyRecord.id)
        .filter(
            StudyLog.material_id.in_(material_ids),
            DailyRecord.record_date >= week_start,
            DailyRecord.record_date <= week_end,
        )
        .order_by(DailyRecord.record_date)
        .all()
    )
    if not rows:
        return "（この週の実績はありません）"
    material_names = {material.id: material.name for material in goal.materials}
    lines = []
    for record_date, material_id, amount, cycle_number, minutes in rows:
        minutes_text = f"{minutes}分" if minutes else "時間未入力"
        lines.append(
            f"・{record_date.isoformat()} {material_names[material_id]}: {amount}"
            f"（{cycle_number}周目、{minutes_text}）"
        )
    return "\n".join(lines)


def build_week_diaries_text(session: Session, week_start: dt.date, week_end: dt.date) -> str:
    """{{week_diaries}}: 週内の日記（行動・所感、学んだこと、17.3）。"""
    records = (
        session.query(DailyRecord)
        .filter(
            DailyRecord.record_date >= week_start,
            DailyRecord.record_date <= week_end,
            DailyRecord.record_state == RecordState.REPORTED,
        )
        .order_by(DailyRecord.record_date)
        .all()
    )
    if not records:
        return "（この週の日記はありません）"
    return "\n\n".join(
        f"【{record.record_date.isoformat()}】\n"
        f"行動・所感: {record.diary_body or ''}\n"
        f"学んだこと: {record.diary_learned or ''}"
        for record in records
    )


def build_week_metrics_text(
    session: Session,
    goal: Goal,
    week_start: dt.date,
    week_end: dt.date,
    treat_holiday_as_buffer: bool,
) -> str:
    """{{week_metrics}}: 週の集計値（総投下時間、総完了量、品質指標平均、報告日数、
    バッファ消費、17.3）。
    """
    material_ids = [material.id for material in goal.materials]
    rows = (
        session.query(StudyLog.amount_completed, StudyLog.minutes_spent, StudyLog.quality_value)
        .join(DailyRecord, StudyLog.daily_record_id == DailyRecord.id)
        .filter(
            StudyLog.material_id.in_(material_ids),
            DailyRecord.record_date >= week_start,
            DailyRecord.record_date <= week_end,
        )
        .all()
        if material_ids
        else []
    )
    total_amount = sum(row.amount_completed for row in rows)
    total_minutes = sum(row.minutes_spent or 0 for row in rows)
    qualities = [row.quality_value for row in rows if row.quality_value is not None]
    avg_quality_text = f"{sum(qualities) / len(qualities):.1f}" if qualities else "データなし"

    reported_days = (
        session.query(DailyRecord.id)
        .filter(
            DailyRecord.record_date >= week_start,
            DailyRecord.record_date <= week_end,
            DailyRecord.record_state == RecordState.REPORTED,
        )
        .count()
    )

    day_types = calendar_service.resolve_day_types(
        session, week_start, week_end, treat_holiday_as_buffer
    )
    buffer_days = [d for d, day_type in day_types.items() if day_type == DayType.BUFFER]
    dates_with_log = (
        {
            row[0]
            for row in session.query(DailyRecord.record_date)
            .join(StudyLog, StudyLog.daily_record_id == DailyRecord.id)
            .filter(DailyRecord.record_date.in_(buffer_days))
            .distinct()
        }
        if buffer_days
        else set()
    )
    buffer_rate_text = (
        f"{len(dates_with_log) / len(buffer_days):.0%}" if buffer_days else "算出不可"
    )

    return (
        f"総投下時間: {total_minutes / 60:.1f}時間\n"
        f"総完了量: {total_amount}\n"
        f"品質指標平均: {avg_quality_text}\n"
        f"報告日数: {reported_days}日\n"
        f"バッファ消費率: {buffer_rate_text}"
    )
