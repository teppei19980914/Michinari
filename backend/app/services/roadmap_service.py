"""道のりマップの算出（開発Todo_道のりマップ_v1.0.md §0・§4）。

目標ごとの進捗を「スタート→現在地→ゴール」の図（資格=山、読書=地図上の道、仕事=足跡の
積み上げ）として可視化するための、正規化された点列（0.0〜1.0の比率）・マイルストーンを
算出する。新しい値はDBに保存せず都度算出する（CLAUDE.md）。SVG座標への変換はフロント側
（roadmapGeometry.ts）が行うため、本サービスは比率と日付のみを返す（§0 U12）。

カテゴリごとの分岐はこのファイル内にまとめ、肥大化した場合のみ
roadmap_service_common.py/_exam.py/_reading.py/_work.py への分割を検討する
（work_report_service等の既存の置き場所ルールに合わせる）。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants.enums import BaselineReason, DayType, GoalCategory
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, ReadingLog, WorkLog
from app.services import (
    analytics_service,
    calendar_service,
    cycle_service,
    goal_service,
    material_service,
    metrics_service,
    speed_service,
    work_report_service,
)
from app.services.cycle_service import ProgressPoint


@dataclass(frozen=True)
class RoadmapPoint:
    """道のり上の1点（比率は0.0〜1.0。資格=標高、読書=ページ進捗、仕事は未使用、§0 U17）。"""

    date: dt.date
    ratio: float


@dataclass(frozen=True)
class RoadmapFootprint:
    """足跡の1件（記録はあるが定量入力が無い日＝読書のページ未入力。仕事は常にTrue）。"""

    date: dt.date
    has_input: bool


@dataclass(frozen=True)
class Roadmap:
    """目標1件分の道のり算出結果（詳細版APIのレスポンス元、§3.1 S-02）。"""

    category: GoalCategory
    start_date: dt.date
    goal_date: dt.date
    today_date: dt.date
    progress_ratio: float
    is_achieved: bool
    planned_points: list[RoadmapPoint]
    actual_points: list[RoadmapPoint]
    footprint_dates: list[RoadmapFootprint]
    replan_marks: list[RoadmapPoint]
    feedback_marks: list[dt.date]
    buffer_dates: list[dt.date]
    overrun_days: float | None


def get_roadmap(
    session: Session, goal: Goal, today: dt.date, treat_holiday_as_buffer: bool
) -> Roadmap:
    """目標種別に応じた道のりを算出する（§0 U4〜U10・U16・U17）。"""
    if goal.category == GoalCategory.EXAM:
        return _exam_roadmap(session, goal, today, treat_holiday_as_buffer)
    if goal.category == GoalCategory.READING:
        return _reading_roadmap(session, goal, today, treat_holiday_as_buffer)
    return _work_roadmap(session, goal, today)


# --- 共通 ---


def _date_range(date_from: dt.date, date_to: dt.date) -> list[dt.date]:
    if date_from > date_to:
        return []
    days = (date_to - date_from).days
    return [date_from + dt.timedelta(days=i) for i in range(days + 1)]


def _feedback_marks(session: Session, goal: Goal) -> list[dt.date]:
    """AIフィードバックを受けた日（道標、§4共通）。

    analytics_service.list_growth_descriptions をそのまま再利用する（CLAUDE.md DRYの原則）。
    AI未設定・フィードバック履歴が無い場合は空配列になり、道標なしで図が成立する（§0 要件6）。
    """
    entries = analytics_service.list_growth_descriptions(session, goal)
    return sorted({entry.record_date for entry in entries})


def resolve_work_period(today: dt.date) -> tuple[dt.date, dt.date]:
    """仕事目標の道の起点・終点＝現評価期間（§0 U9）。dashboard.py の縮小版からも参照する
    （DRYの原則、_work_roadmapと同じ算出を複製しない）。"""
    period_key = work_report_service.default_semiannual_period_key(today)
    return work_report_service.semiannual_period_range(period_key)


def compute_elapsed_ratio(start_date: dt.date, goal_date: dt.date, today: dt.date) -> float:
    """期間に対する経過日数の割合（0.0〜1.0にクランプ）。仕事目標の「現在地」に使う（§0 U17）。"""
    total_days = (goal_date - start_date).days
    if total_days <= 0:
        return 1.0
    return min(max((today - start_date).days / total_days, 0.0), 1.0)


# --- EXAM（山） ---


def _material_total_work(material: Material) -> float:
    return material.total_amount * material.planned_cycles


def _ratio_series(
    points: list[ProgressPoint],
    total_work: float,
    date_from: dt.date,
    date_to: dt.date,
) -> dict[dt.date, float]:
    """累積量の点列を、日次の比率（0.0起点、直前の値を保持するステップ関数）へ変換する。

    記録・計画が1件も無い場合（境界ケース：記録0件）も、date_from〜date_toの全日付が
    比率0.0で埋まった辞書を返し、呼び出し側を分岐させない。
    """
    series: dict[dt.date, float] = {}
    if total_work <= 0 or date_from > date_to:
        return series
    by_date = {p.record_date: min(p.cumulative_completed / total_work, 1.0) for p in points}
    current = 0.0
    d = date_from
    while d <= date_to:
        if d in by_date:
            current = by_date[d]
        series[d] = current
        d += dt.timedelta(days=1)
    return series


def _extend_to_range(
    series: dict[dt.date, float], date_from: dt.date, date_to: dt.date
) -> dict[dt.date, float]:
    """教材固有の日付範囲で算出した比率系列を、目標全体の範囲へ延長する。

    範囲開始より前は0.0（まだ始まっていない）、範囲終了より後は最後の値を保持する
    （締切超過後も到達済みの比率を描き続ける＝境界ケース：ゴール超過）。
    """
    if not series:
        return dict.fromkeys(_date_range(date_from, date_to), 0.0)
    first, last = min(series), max(series)
    last_value = series[last]
    extended: dict[dt.date, float] = {}
    for d in _date_range(date_from, date_to):
        if d < first:
            extended[d] = 0.0
        elif d > last:
            extended[d] = last_value
        else:
            extended[d] = series[d]
    return extended


def _average_series(
    series_list: list[dict[dt.date, float]], date_from: dt.date, date_to: dt.date
) -> list[RoadmapPoint]:
    """複数教材の比率系列を日次で単純平均し、目標単位の1本に合成する（§0 U6）。

    呼び出し側（_exam_roadmap）は各系列を_extend_to_rangeで必ずdate_from〜date_toの
    全日付を含む形に揃えて渡すため、ここでは欠損日の存在を考慮しない。
    """
    if not series_list:
        return []
    return [
        RoadmapPoint(date=d, ratio=sum(series[d] for series in series_list) / len(series_list))
        for d in _date_range(date_from, date_to)
    ]


def _replan_marks(session: Session, goal: Goal) -> list[RoadmapPoint]:
    """道の引き直し目印（EXAMのみ、§0 U10）。INITIALは初回の計画であり「引き直し」では
    ないため対象外とする（BaselineReasonのdocstring「実際の再設定はMATERIAL_CHANGED・
    CYCLE_CHANGED・EXAM_DATE_FIXEDのいずれかとして記録される」に基づく）。
    """
    total_work_by_material = {m.id: _material_total_work(m) for m in goal.materials}
    marks: list[RoadmapPoint] = []
    for baseline in goal_service.get_baselines(session, goal):
        if baseline.reason == BaselineReason.INITIAL:
            continue
        total_work = total_work_by_material.get(baseline.material_id)
        if total_work is None or total_work <= 0:
            continue
        completed_at_baseline = total_work - baseline.remaining_at_baseline
        ratio = min(max(completed_at_baseline / total_work, 0.0), 1.0)
        marks.append(RoadmapPoint(date=baseline.effective_from, ratio=ratio))
    marks.sort(key=lambda m: m.date)
    return marks


def _buffer_dates(
    session: Session, start_date: dt.date, goal_date: dt.date, treat_holiday_as_buffer: bool
) -> list[dt.date]:
    """予備日（UI-07）。バッファ日（`day_type`）はカテゴリに依存しないアプリ全体のカレンダー
    概念のため、仕様書13.5の既定方針どおり資格試験・読書目標が対象、仕事目標は対象外
    （§0 U8訂正、2026-10-30。計算量カバレッジはEXAM専用の`compute_buffer_usage_rate`とは
    別の指標であり、バッファ日の存在自体はカテゴリに依存しない）。"""
    day_types = calendar_service.resolve_day_types(
        session, start_date, goal_date, treat_holiday_as_buffer
    )
    return sorted(d for d, day_type in day_types.items() if day_type == DayType.BUFFER)


def _average_overrun_days(
    session: Session,
    goal: Goal,
    materials: list[Material],
    today: dt.date,
    treat_holiday_as_buffer: bool,
) -> float | None:
    """完了予測日と締切の平均乖離日数（EXAMのみ、§0 U7・U16）。dashboard.pyの
    forecast_deviation_daysと同じ算出（CLAUDE.md DRYの原則。将来的に共通化を検討）。
    """
    if not materials:
        return None
    deviations = [
        forecast.overrun_days
        for forecast in (
            speed_service.compute_forecast_date(
                session, goal, m, materials, today, treat_holiday_as_buffer
            )
            for m in materials
        )
        if forecast.overrun_days is not None
    ]
    return sum(deviations) / len(deviations) if deviations else None


def _exam_roadmap(
    session: Session, goal: Goal, today: dt.date, treat_holiday_as_buffer: bool
) -> Roadmap:
    materials = material_service.list_active_materials(goal)
    start_date = goal.start_date
    # 山頂の日付＝全科目中の最も遅い有効受験日（§0 U4）。科目未登録（下書き中）は山頂を
    # 決められないため、開始日自体を暫定の山頂とする（境界ケース：記録0件）。
    goal_date = (
        max(material_service.effective_exam_date(s) for s in goal.exam_subjects)
        if goal.exam_subjects
        else start_date
    )
    overall_to = max(goal_date, today)

    progress_ratio = (
        sum(
            metrics_service.compute_progress_rate(cycle_service.get_material_progress(session, m))
            for m in materials
        )
        / len(materials)
        if materials
        else 0.0
    )

    plan_series = [
        _extend_to_range(
            _ratio_series(
                analytics_service.compute_plan_line(session, m, treat_holiday_as_buffer),
                _material_total_work(m),
                m.start_date,
                m.due_date,
            ),
            start_date,
            overall_to,
        )
        for m in materials
    ]
    actual_series = [
        _extend_to_range(
            _ratio_series(
                cycle_service.compute_cumulative_progress(session, m.id),
                _material_total_work(m),
                m.start_date,
                max(m.due_date, overall_to),
            ),
            start_date,
            overall_to,
        )
        for m in materials
    ]

    return Roadmap(
        category=GoalCategory.EXAM,
        start_date=start_date,
        goal_date=goal_date,
        today_date=today,
        progress_ratio=progress_ratio,
        is_achieved=progress_ratio >= 1.0,
        planned_points=_average_series(plan_series, start_date, overall_to),
        actual_points=_average_series(actual_series, start_date, overall_to),
        footprint_dates=[],
        replan_marks=_replan_marks(session, goal),
        feedback_marks=_feedback_marks(session, goal),
        buffer_dates=_buffer_dates(session, start_date, goal_date, treat_holiday_as_buffer),
        overrun_days=_average_overrun_days(
            session, goal, materials, today, treat_holiday_as_buffer
        ),
    )


# --- READING（道） ---


def _reading_roadmap(
    session: Session, goal: Goal, today: dt.date, treat_holiday_as_buffer: bool
) -> Roadmap:
    book = goal.book
    if book is None:
        # 書籍未登録（下書き中）。境界ケース：記録0件と同様、空の道として成立させる。
        start_date = goal.start_date
        return Roadmap(
            category=GoalCategory.READING,
            start_date=start_date,
            goal_date=start_date,
            today_date=today,
            progress_ratio=0.0,
            is_achieved=False,
            planned_points=[],
            actual_points=[],
            footprint_dates=[],
            replan_marks=[],
            feedback_marks=_feedback_marks(session, goal),
            buffer_dates=_buffer_dates(session, start_date, start_date, treat_holiday_as_buffer),
            overrun_days=None,
        )

    # record_date・current_pageをまとめて1クエリで取得する（N+1禁止、CLAUDE.md。
    # book_service.get_book_progressと同じ結合だが、全件を日付昇順の時系列として使う点が
    # 異なるため専用に取得する）。
    rows = (
        session.query(DailyRecord.record_date, ReadingLog.current_page)
        .join(ReadingLog, ReadingLog.daily_record_id == DailyRecord.id)
        .filter(ReadingLog.book_id == book.id)
        .order_by(DailyRecord.record_date)
        .all()
    )

    start_date = book.start_date
    goal_date = book.due_date

    current_page: int | None = None
    actual_points: list[RoadmapPoint] = []
    footprints: list[RoadmapFootprint] = []
    for record_date, page in rows:
        if page is not None:
            current_page = page
            actual_points.append(
                RoadmapPoint(date=record_date, ratio=min(current_page / book.total_pages, 1.0))
            )
        else:
            # ページ未入力の記録日は足跡として置く（§0 要件、current_pageは更新しない）。
            footprints.append(RoadmapFootprint(date=record_date, has_input=False))

    progress_ratio = actual_points[-1].ratio if actual_points else 0.0

    # 計画線＝開始日からゴール（最終ページ）までの日数按分の直線（§0 U7「計画との差は
    # 線のズレ自体で表現」）。ゴールを過ぎた日は1.0のまま延長する（境界ケース：ゴール超過）。
    total_days = (goal_date - start_date).days
    overall_to = max(goal_date, today)
    planned_points = [
        RoadmapPoint(
            date=d,
            ratio=(
                1.0
                if d >= goal_date or total_days <= 0
                else min((d - start_date).days / total_days, 1.0)
            ),
        )
        for d in _date_range(start_date, overall_to)
    ]

    return Roadmap(
        category=GoalCategory.READING,
        start_date=start_date,
        goal_date=goal_date,
        today_date=today,
        progress_ratio=progress_ratio,
        is_achieved=progress_ratio >= 1.0,
        planned_points=planned_points,
        actual_points=actual_points,
        footprint_dates=footprints,
        replan_marks=[],  # §0 U10：読書に計画基準値の概念が無いため表示しない
        feedback_marks=_feedback_marks(session, goal),
        # 予備日（UI-07）は仕様書13.5の既定方針どおり読書も対象（§0 U8訂正、2026-10-30）。
        buffer_dates=_buffer_dates(session, start_date, goal_date, treat_holiday_as_buffer),
        overrun_days=None,  # §0 U7：進捗状態の判定は新設しない
    )


# --- WORK（足跡の積み上げ） ---


def _work_roadmap(session: Session, goal: Goal, today: dt.date) -> Roadmap:
    start_date, goal_date = resolve_work_period(today)

    footprints: list[RoadmapFootprint] = []
    work_assignment = goal.work_assignment
    if work_assignment is not None:
        rows = (
            session.query(DailyRecord.record_date)
            .join(WorkLog, WorkLog.daily_record_id == DailyRecord.id)
            .filter(
                WorkLog.work_assignment_id == work_assignment.id,
                DailyRecord.record_date >= start_date,
                DailyRecord.record_date <= goal_date,
            )
            .order_by(DailyRecord.record_date)
            .all()
        )
        footprints = [RoadmapFootprint(date=row[0], has_input=True) for row in rows]

    return Roadmap(
        category=GoalCategory.WORK,
        start_date=start_date,
        goal_date=goal_date,
        today_date=today,
        progress_ratio=compute_elapsed_ratio(start_date, goal_date, today),
        # resolve_work_periodは常にtodayを含む期間を返すため、「ゴール超過」は構造的に
        # 発生しない。期間最終日（ゴール当日）を達成扱いとする（>=）。
        is_achieved=today >= goal_date,
        planned_points=[],  # §0 U17：進捗量の概念が無いため計画線・実績線は描かない
        actual_points=[],  # §0 U17
        footprint_dates=footprints,
        replan_marks=[],  # §0 U10
        feedback_marks=_feedback_marks(session, goal),
        # 予備日（UI-07）は仕様書13.5のとおり仕事目標のみ対象外（§0 U8訂正、2026-10-30）。
        buffer_dates=[],
        overrun_days=None,  # §0 U7
    )
