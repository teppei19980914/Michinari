"""資格試験テンプレートのAPI（実装フェーズ分割計画書Phase38）。"""

from fastapi import APIRouter

from app.schemas.exam_template import ExamTemplateRead
from app.services import exam_template_service

router = APIRouter(tags=["exam-templates"])


@router.get("/exam-templates", response_model=list[ExamTemplateRead])
def get_exam_templates() -> list[ExamTemplateRead]:
    return exam_template_service.list_exam_templates()
