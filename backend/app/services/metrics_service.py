"""補助指標の算出（設計書 ロジック・プロンプト編 13章）と品質指標の正規化（14章）。"""

import datetime as dt
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.constants.enums import BaselineReason, DayType, QualityMetricType, RecordState
from app.models.goal import Goal
from app.models.material import Material, PlanBaseline
from app.models.record import DailyRecord, StudyLog
from app.services import calendar_service
from app.services.cycle_service import MaterialProgress

#: SUBJECTIVE（主観的手応え5段階）の正規化テーブル（14.1）。
_SUBJECTIVE_NORMALIZATION_TABLE = {1: 20.0, 2: 40.0, 3: 60.0, 4: 80.0, 5: 100.0}


def compute_buffer_usage_rate(
    session: Session, goal: Goal, today: dt.date, treat_holiday_as_buffer: bool
) -> float | None:
    """バッファ消費率を算出する（13.1）。経過バッファ日が0件の場合は算出不能（None）。"""
    if today <= goal.start_date:
        return None

    day_types = calendar_service.resolve_day_types(
        session, goal.start_date, today - dt.timedelta(days=1), treat_holiday_as_buffer
    )
    buffer_days = [d for d, day_type in day_types.items() if day_type == DayType.BUFFER]
    if not buffer_days:
        return None

    dates_with_study_log = {
        row[0]
        for row in session.query(DailyRecord.record_date)
        .join(StudyLog, StudyLog.daily_record_id == DailyRecord.id)
        .filter(DailyRecord.record_date.in_(buffer_days))
        .distinct()
    }
    return len(dates_with_study_log) / len(buffer_days)


def compute_progress_rate(progress: MaterialProgress) -> float:
    """教材の全体進捗率 progress_rate(m) を算出する（13.2）。"""
    if progress.total_work <= 0:
        return 0.0
    return progress.completed / progress.total_work


def compute_report_rate(session: Session, goal: Goal, today: dt.date) -> float:
    """報告率（KPI）を算出する（13.3）。"""
    total_days = (today - goal.start_date).days + 1
    if total_days <= 0:
        return 0.0

    reported = (
        session.query(func.count(DailyRecord.id))
        .filter(
            DailyRecord.record_date >= goal.start_date,
            DailyRecord.record_date <= today,
            DailyRecord.record_state == RecordState.REPORTED,
        )
        .scalar()
        or 0
    )
    return reported / total_days


def compute_recent_report_rate(
    session: Session, goal: Goal, today: dt.date, window_days: int
) -> float:
    """直近window_days日間の報告率を算出する（仕様書6.1「直近30日の報告率」）。

    13.3の報告率（目標開始日からの通算KPI）とは窓が異なる派生指標。目標開始日から
    今日までの経過日数がwindow_days未満の場合は、経過日数のみを母数とする
    （compute_report_rateと同様、開始日以前を母数に含めない）。
    """
    total_days = (today - goal.start_date).days + 1
    if total_days <= 0:
        return 0.0
    window_start = max(goal.start_date, today - dt.timedelta(days=window_days - 1))
    window_size = (today - window_start).days + 1

    reported = (
        session.query(func.count(DailyRecord.id))
        .filter(
            DailyRecord.record_date >= window_start,
            DailyRecord.record_date <= today,
            DailyRecord.record_state == RecordState.REPORTED,
        )
        .scalar()
        or 0
    )
    return reported / window_size


def compute_consecutive_report_days(
    session: Session, goal: Goal, today: dt.date, treat_holiday_as_buffer: bool
) -> int:
    """連続報告日数を算出する（13.4）。BUFFER/OFF日は報告がなくても連続を中断しない。"""
    if today < goal.start_date:
        return 0

    day_types = calendar_service.resolve_day_types(
        session, goal.start_date, today, treat_holiday_as_buffer
    )
    reported_dates = {
        row[0]
        for row in session.query(DailyRecord.record_date).filter(
            DailyRecord.record_date >= goal.start_date,
            DailyRecord.record_date <= today,
            DailyRecord.record_state == RecordState.REPORTED,
        )
    }

    count = 0
    current_date = today
    while current_date >= goal.start_date:
        if current_date in reported_dates:
            count += 1
        elif day_types.get(current_date) in (DayType.BUFFER, DayType.OFF):
            pass
        else:
            break
        current_date -= dt.timedelta(days=1)

    return count


def compute_replan_count(session: Session, goal: Goal) -> int:
    """リプラン回数を算出する（13.5）。INITIAL以外の plan_baseline レコード数。"""
    return (
        session.query(func.count(PlanBaseline.id))
        .join(Material, PlanBaseline.material_id == Material.id)
        .filter(Material.goal_id == goal.id, PlanBaseline.reason != BaselineReason.INITIAL)
        .scalar()
        or 0
    )


def normalize_quality_value(
    metric_type: QualityMetricType, raw_value: float | int | None
) -> float | None:
    """品質指標を0〜100へ正規化する（14.1）。"""
    if metric_type == QualityMetricType.NONE or raw_value is None:
        return None

    if metric_type in (QualityMetricType.OBJECTIVE, QualityMetricType.SELF_SCORED):
        return float(raw_value)

    # QualityMetricTypeは4種のみ（5.1）。ここに到達する場合は残るSUBJECTIVEで確定する。
    score = int(raw_value)
    if score not in _SUBJECTIVE_NORMALIZATION_TABLE:
        raise ValueError(f"主観的手応えは1〜5で入力してください（入力値: {raw_value}）")
    return _SUBJECTIVE_NORMALIZATION_TABLE[score]


def group_quality_by_cycle(session: Session, material_id: int) -> dict[int, list[float]]:
    """品質指標を周回別に系列分離する（14.3）。"""
    rows = (
        session.query(StudyLog.cycle_number, StudyLog.quality_value)
        .filter(StudyLog.material_id == material_id, StudyLog.quality_value.isnot(None))
        .all()
    )
    grouped: dict[int, list[float]] = defaultdict(list)
    for cycle_number, quality_value in rows:
        grouped[cycle_number].append(quality_value)
    return dict(grouped)
