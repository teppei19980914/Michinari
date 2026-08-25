"""分析のAPI（仕様書6.8 SC-09、データ構造編8章、実装フェーズ分割計画書Phase9）。

Phase2〜5で実装・テスト済みのサービス（cycle_service・metrics_service・speed_service・
analytics_service・material_service）を呼び出して組み立てるだけの薄い層（データ構造編8.1
「api層: 業務ロジックの記述」禁止、dashboard.pyと同じ方針）。

データ構造編8章のエンドポイント一覧では /analytics/quality・progress・forecast・speed・
gantt の5件のみが明記されているが、仕様書6.8の成長記述タブ（ANL-07、MVP）に対応する
エンドポイントが列挙から漏れているため、/analytics/growth-descriptions を追加した
（Phase9実装判断、根拠はanalytics_service.list_growth_descriptionsのdocstring参照）。
リプラン履歴タブは既存の GET /goals/{goal_id}/baselines をそのまま利用する
（Phase3で実装済み、新規エンドポイントを追加しない）。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.app_setting_keys import DISPLAY_DEFAULT_GRANULARITY
from app.constants.enums import Granularity
from app.database import get_db
from app.models.goal import Goal
from app.models.material import Material
from app.schemas.analytics import (
    CycleBoundaryRead,
    ForecastAnalyticsRead,
    ForecastEntryRead,
    GanttAnalyticsRead,
    GanttEntryRead,
    GrowthDescriptionEntryRead,
    MaterialProgressTrendRead,
    MaterialQualityTrendRead,
    MaterialSpeedTrendRead,
    ProgressAnalyticsRead,
    ProgressPointRead,
    QualityAnalyticsRead,
    QualityTrendPointRead,
    QualityTrendSeriesRead,
    SpeedAnalyticsRead,
    SpeedTrendPointRead,
    SpeedTrendSeriesRead,
)
from app.services import (
    analytics_service,
    cycle_service,
    goal_service,
    material_service,
    metrics_service,
    setting_reader,
    speed_service,
)

router = APIRouter(tags=["analytics"])


def _get_goal_and_active_materials(session: Session, goal_id: int) -> tuple[Goal, list[Material]]:
    goal = goal_service.get_goal(session, goal_id)
    return goal, material_service.list_active_materials(goal)


@router.get("/analytics/quality", response_model=QualityAnalyticsRead)
def get_quality_analytics(
    goal_id: int,
    granularity: Granularity | None = None,
    session: Session = Depends(get_db),
) -> QualityAnalyticsRead:
    _, materials = _get_goal_and_active_materials(session, goal_id)
    resolved_granularity = granularity or Granularity(
        setting_reader.get_str(session, DISPLAY_DEFAULT_GRANULARITY)
    )

    materials_out = []
    for material in materials:
        trend = metrics_service.compute_quality_trend(session, material.id, resolved_granularity)
        materials_out.append(
            MaterialQualityTrendRead(
                material_id=material.id,
                material_name=material.name,
                passing_score=metrics_service.resolve_passing_score(material),
                series=[
                    QualityTrendSeriesRead(
                        cycle_number=cycle_number,
                        points=[
                            QualityTrendPointRead(
                                period_start=p.period_start,
                                value=p.value,
                                sample_count=p.sample_count,
                            )
                            for p in points
                        ],
                    )
                    for cycle_number, points in sorted(trend.items())
                ],
            )
        )
    return QualityAnalyticsRead(granularity=resolved_granularity, materials=materials_out)


@router.get("/analytics/progress", response_model=ProgressAnalyticsRead)
def get_progress_analytics(
    goal_id: int, session: Session = Depends(get_db)
) -> ProgressAnalyticsRead:
    _, materials = _get_goal_and_active_materials(session, goal_id)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)

    materials_out = []
    for material in materials:
        actual_points = cycle_service.compute_cumulative_progress(session, material.id)
        plan_points = analytics_service.compute_plan_line(
            session, material, treat_holiday_as_buffer
        )
        boundaries = cycle_service.compute_cycle_boundaries(material, actual_points)
        materials_out.append(
            MaterialProgressTrendRead(
                material_id=material.id,
                material_name=material.name,
                unit_label=material.unit_label,
                total_work=material.total_amount * material.planned_cycles,
                actual_points=[
                    ProgressPointRead(
                        record_date=p.record_date, cumulative_completed=p.cumulative_completed
                    )
                    for p in actual_points
                ],
                plan_points=[
                    ProgressPointRead(
                        record_date=p.record_date, cumulative_completed=p.cumulative_completed
                    )
                    for p in plan_points
                ],
                cycle_boundaries=[
                    CycleBoundaryRead(cycle_number=b.cycle_number, record_date=b.record_date)
                    for b in boundaries
                ],
            )
        )
    return ProgressAnalyticsRead(materials=materials_out)


@router.get("/analytics/forecast", response_model=ForecastAnalyticsRead)
def get_forecast_analytics(
    goal_id: int, session: Session = Depends(get_db)
) -> ForecastAnalyticsRead:
    goal, materials = _get_goal_and_active_materials(session, goal_id)
    today = goal_service.resolve_today(session)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)

    materials_out = []
    for material in materials:
        forecast = speed_service.compute_forecast_date(
            session, goal, material, materials, today, treat_holiday_as_buffer
        )
        materials_out.append(
            ForecastEntryRead(
                material_id=material.id,
                material_name=material.name,
                unit_label=material.unit_label,
                due_date=material.due_date,
                forecast_date=forecast.forecast_date,
                overrun_days=forecast.overrun_days,
                unavailable_reason=(
                    forecast.unavailable_reason.value if forecast.unavailable_reason else None
                ),
            )
        )
    return ForecastAnalyticsRead(materials=materials_out)


@router.get("/analytics/speed", response_model=SpeedAnalyticsRead)
def get_speed_analytics(goal_id: int, session: Session = Depends(get_db)) -> SpeedAnalyticsRead:
    _, materials = _get_goal_and_active_materials(session, goal_id)

    materials_out = []
    for material in materials:
        trend = speed_service.compute_speed_trend(session, material.id)
        materials_out.append(
            MaterialSpeedTrendRead(
                material_id=material.id,
                material_name=material.name,
                unit_label=material.unit_label,
                series=[
                    SpeedTrendSeriesRead(
                        cycle_number=cycle_number,
                        points=[
                            SpeedTrendPointRead(record_date=p.record_date, speed=p.speed)
                            for p in points
                        ],
                    )
                    for cycle_number, points in sorted(trend.items())
                ],
            )
        )
    return SpeedAnalyticsRead(materials=materials_out)


@router.get("/analytics/gantt", response_model=GanttAnalyticsRead)
def get_gantt_analytics(goal_id: int, session: Session = Depends(get_db)) -> GanttAnalyticsRead:
    _, materials = _get_goal_and_active_materials(session, goal_id)
    today = goal_service.resolve_today(session)

    materials_out = []
    for material in materials:
        progress = cycle_service.get_material_progress(session, material)
        materials_out.append(
            GanttEntryRead(
                material_id=material.id,
                material_name=material.name,
                start_date=material.start_date,
                due_date=material.due_date,
                progress_rate=metrics_service.compute_progress_rate(progress),
                current_cycle=progress.current_cycle,
                planned_cycles=material.planned_cycles,
            )
        )
    return GanttAnalyticsRead(today=today, materials=materials_out)


@router.get("/analytics/growth-descriptions", response_model=list[GrowthDescriptionEntryRead])
def get_growth_descriptions(
    session: Session = Depends(get_db),
) -> list[GrowthDescriptionEntryRead]:
    entries = analytics_service.list_growth_descriptions(session)
    return [
        GrowthDescriptionEntryRead(record_date=e.record_date, content=e.content) for e in entries
    ]
