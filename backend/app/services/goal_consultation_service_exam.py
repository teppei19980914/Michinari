"""目標相談チャット（資格目標、S09）のカテゴリ別の変数組み立て（開発Todo v1.1 V5）。

カテゴリ非依存の処理は`goal_consultation_service_common.py`を参照。既存の`build_*`関数を
そのまま再利用し、再実装しない（S09開発Todo 要件1）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.enums import AiPurpose
from app.models.goal import Goal
from app.services import ai_context_exam
from app.services.goal_consultation_service_common import CategoryContext


def build_context(session: Session, goal: Goal, today: dt.date) -> CategoryContext:
    """{{goal_summary}}・{{exam_results}}・{{material_summary}}・{{quality_trend}}・
    {{replan_history}}と{{recent_logs}}の生ログを組み立てる。"""
    materials = [material for material in goal.materials if material.is_active]
    fixed_variables = {
        "goal_summary": ai_context_exam.build_goal_summary([goal], today),
        "exam_results": ai_context_exam.build_exam_results_text(session, goal),
        "material_summary": ai_context_exam.build_material_summary_text(session, materials),
        "quality_trend": ai_context_exam.build_quality_trend_text(session, materials),
        "replan_history": ai_context_exam.build_replan_history_text(session, goal),
    }
    raw_entries = ai_context_exam.build_recent_study_entries(session, goal, goal.start_date, today)
    return CategoryContext(
        purpose=AiPurpose.GOAL_CONSULTATION,
        fixed_variables=fixed_variables,
        raw_entries=raw_entries,
    )
