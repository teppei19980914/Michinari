"""補助指標の算出（設計書 ロジック・プロンプト編 13章）と品質指標の正規化（14章）。"""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.constants.enums import BaselineReason, DayType, Granularity, QualityMetricType, RecordState
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


@dataclass(frozen=True)
class StudySummary:
    """総投下時間・学習日数の集計結果（総括レポート・ナレッジエクスポート双方の
    学習量サマリで使う、実装フェーズ分割計画書Phase10）。"""

    total_minutes: int
    study_days: int


def compute_study_summary(session: Session, material_ids: list[int]) -> StudySummary:
    """教材群の総投下時間（分）・学習日数を集計する（総括レポート17.5
    {{overall_metrics}}、ナレッジエクスポート7.1 summary.total_minutes/study_daysの
    共通算出処理。export_service.pyとai_context_service.pyの双方から呼ぶ、
    CLAUDE.md DRYの原則）。"""
    if not material_ids:
        return StudySummary(total_minutes=0, study_days=0)

    total_minutes = (
        session.query(func.sum(StudyLog.minutes_spent))
        .filter(StudyLog.material_id.in_(material_ids))
        .scalar()
        or 0
    )
    study_days = (
        session.query(func.count(func.distinct(DailyRecord.record_date)))
        .join(StudyLog, StudyLog.daily_record_id == DailyRecord.id)
        .filter(StudyLog.material_id.in_(material_ids))
        .scalar()
        or 0
    )
    return StudySummary(total_minutes=total_minutes, study_days=study_days)


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


@dataclass(frozen=True)
class QualityTrendPoint:
    """品質推移グラフの1点（分析画面ANL-01、14.2の集約規則で平均化済み）。"""

    period_start: dt.date
    value: float
    sample_count: int


def _bucket_start(record_date: dt.date, granularity: Granularity) -> dt.date:
    """粒度に応じた集計区間の開始日を返す（14.2、15.1と同じ「月曜始まり」の週定義）。"""
    if granularity == Granularity.DAY:
        return record_date
    if granularity == Granularity.WEEK:
        return record_date - dt.timedelta(days=record_date.weekday())
    return record_date.replace(day=1)


def compute_quality_trend(
    session: Session, material_id: int, granularity: Granularity
) -> dict[int, list[QualityTrendPoint]]:
    """品質指標推移を周回別・粒度別に集計する（14.2集約規則、14.3周回別系列分離、
    分析画面ANL-01・ANL-03）。加重平均ではなく単純平均とする（14.2）。
    """
    rows = (
        session.query(StudyLog.cycle_number, StudyLog.quality_value, DailyRecord.record_date)
        .join(DailyRecord, StudyLog.daily_record_id == DailyRecord.id)
        .filter(StudyLog.material_id == material_id, StudyLog.quality_value.isnot(None))
        .all()
    )
    buckets: dict[tuple[int, dt.date], list[float]] = defaultdict(list)
    for cycle_number, quality_value, record_date in rows:
        buckets[(cycle_number, _bucket_start(record_date, granularity))].append(quality_value)

    grouped: dict[int, list[QualityTrendPoint]] = defaultdict(list)
    for (cycle_number, period_start), values in buckets.items():
        grouped[cycle_number].append(
            QualityTrendPoint(
                period_start=period_start,
                value=sum(values) / len(values),
                sample_count=len(values),
            )
        )
    for series in grouped.values():
        series.sort(key=lambda p: p.period_start)
    return dict(grouped)


def resolve_passing_score(material: Material) -> float | None:
    """合格基準線の値を解決する（14.4）。複数科目に紐づく場合は最も高いpassing_scoreを採用する。"""
    scores = [
        link.subject.passing_score
        for link in material.subject_links
        if link.subject.passing_score is not None
    ]
    return max(scores) if scores else None
