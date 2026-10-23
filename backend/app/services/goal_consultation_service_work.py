"""目標相談チャット（仕事目標、S10）のカテゴリ別の変数組み立て（開発Todo v1.1 V5）。

カテゴリ非依存の処理は`goal_consultation_service_common.py`を参照。既存の`build_*`関数を
そのまま再利用し、再実装しない（資格のgoal_consultation_service_exam.pyと同じ方針）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.enums import AiPurpose
from app.models.goal import Goal
from app.services import ai_context_work, work_member_service
from app.services.goal_consultation_service_common import CategoryContext

#: 案件が未登録（WORK目標作成直後でWorkAssignmentTabから案件情報を入力する前）の場合の表示。
_NO_WORK_ASSIGNMENT_TEXT = "（案件が登録されていません）"


def build_context(session: Session, goal: Goal, today: dt.date) -> CategoryContext:
    """{{work_summary}}・{{work_progress}}・{{member_summary}}と{{recent_logs}}の
    生ログを組み立てる。

    品質指標の推移・リプラン履歴に相当する概念が仕事目標に無いため、代わりに案件の概要・
    進み具合の2項目とし、既存の評価レポートと同様にチームメンバー情報も含める
    （利用者確認済み、開発Todo v1.1 V3・V11）。
    """
    work_assignment = goal.work_assignment
    if work_assignment is None:
        fixed_variables = {
            "work_summary": _NO_WORK_ASSIGNMENT_TEXT,
            "work_progress": _NO_WORK_ASSIGNMENT_TEXT,
            "member_summary": _NO_WORK_ASSIGNMENT_TEXT,
        }
        raw_entries = []
    else:
        members = work_member_service.list_active_members(work_assignment)
        fixed_variables = {
            "work_summary": ai_context_work.build_retrospective_work_summary_text(
                work_assignment
            ),
            "work_progress": ai_context_work.build_work_progress_summary(
                session, [work_assignment], today
            ),
            "member_summary": ai_context_work.build_member_summary_text(session, members),
        }
        raw_entries = ai_context_work.build_recent_work_logs_entries(
            session, [work_assignment], goal.start_date, today
        )
    return CategoryContext(
        purpose=AiPurpose.GOAL_CONSULTATION_WORK,
        fixed_variables=fixed_variables,
        raw_entries=raw_entries,
    )
