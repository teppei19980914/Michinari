"""ナレッジエクスポートのAPI（仕様書6.10 SC-13、データ構造編6.2、
実装フェーズ分割計画書Phase10）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.export import (
    KnowledgeExportContentRead,
    KnowledgeExportProgressRead,
    KnowledgeExportRequest,
    KnowledgeExportResultRead,
)
from app.services import export_progress, export_service, goal_service

router = APIRouter(tags=["export"])


def _selection_from_query(
    goal_overview: Annotated[bool, Query()] = True,
    materials: Annotated[bool, Query()] = True,
    summary: Annotated[bool, Query()] = True,
    daily_records: Annotated[bool, Query()] = True,
    quality_trend: Annotated[bool, Query()] = True,
    replan_history: Annotated[bool, Query()] = True,
    weekly_summaries: Annotated[bool, Query()] = True,
    diary: Annotated[bool, Query()] = False,
    ai_dialogue: Annotated[bool, Query()] = False,
    exam_results: Annotated[bool, Query()] = True,
    retrospective: Annotated[bool, Query()] = True,
) -> export_service.ExportSelection:
    return export_service.ExportSelection(
        goal_overview=goal_overview,
        materials=materials,
        summary=summary,
        daily_records=daily_records,
        quality_trend=quality_trend,
        replan_history=replan_history,
        weekly_summaries=weekly_summaries,
        diary=diary,
        ai_dialogue=ai_dialogue,
        exam_results=exam_results,
        retrospective=retrospective,
    )


@router.get(
    "/goals/{goal_id}/knowledge-export/preview", response_model=KnowledgeExportContentRead
)
def preview_knowledge_export(
    goal_id: int,
    anonymized: bool = False,
    selection: export_service.ExportSelection = Depends(_selection_from_query),
    session: Session = Depends(get_db),
) -> KnowledgeExportContentRead:
    """プレビュー（読み取りのみ。匿名化版の再生成は行わず、既存レコードのみを参照する）。"""
    goal = goal_service.get_goal(session, goal_id)
    today = goal_service.resolve_today(session)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    data = export_service.build_export_data(
        session,
        goal,
        selection,
        today=today,
        treat_holiday_as_buffer=treat_holiday_as_buffer,
        anonymized=anonymized,
    )
    markdown = export_service.render_markdown(data, selection)
    return KnowledgeExportContentRead(data=data, markdown=markdown)


@router.get(
    "/goals/{goal_id}/knowledge-export/progress", response_model=KnowledgeExportProgressRead
)
def get_knowledge_export_progress(goal_id: int) -> KnowledgeExportProgressRead:
    """匿名化エクスポート実行中の進捗をポーリングで取得する（Phase10注意点「進捗を表示
    すること」）。DBアクセスを伴わないため、実行中の POST 処理と並行して呼び出せる。
    """
    progress = export_progress.get(goal_id)
    if progress is None:
        return KnowledgeExportProgressRead(in_progress=False)
    return KnowledgeExportProgressRead(
        in_progress=True, completed=progress.completed, total=progress.total
    )


@router.post("/goals/{goal_id}/knowledge-export", response_model=KnowledgeExportResultRead)
def execute_knowledge_export(
    goal_id: int, payload: KnowledgeExportRequest, session: Session = Depends(get_db)
) -> KnowledgeExportResultRead:
    goal = goal_service.get_goal(session, goal_id)
    fields = payload.model_dump(exclude={"anonymize"})
    selection = export_service.ExportSelection(**fields)
    content = export_service.execute_export(session, goal, selection, anonymize=payload.anonymize)
    session.commit()
    return KnowledgeExportResultRead(
        data=content.data,
        markdown=content.markdown,
        markdown_path=str(content.markdown_path),
        json_path=str(content.json_path),
    )
