"""案件情報のAPI補助（データ構造編6.2、実装フェーズ分割計画書Phase21）。

serialize_work_assignment は goals.py（目標詳細への案件情報ネスト表示、および
案件情報作成・更新エンドポイントの応答組み立て）から使う共通処理（CLAUDE.md DRYの原則、
api/books.pyのserialize_bookと同じ位置づけ）。案件情報の作成・更新は書籍と異なり、
目標配下のネストパス（POST/PATCH /goals/{id}/work-assignment）に統一するため、
bookのような独立リソースパス用のルーターはここには置かない（データ構造編6.2）。
"""

from sqlalchemy.orm import Session

from app.models.work import WorkAssignment, WorkEvaluationReport, WorkMember
from app.schemas.work import WorkAssignmentRead, WorkMemberRead
from app.schemas.work_evaluation import WorkEvaluationReportRead
from app.services import goal_service, work_service


def serialize_work_member(member: WorkMember) -> WorkMemberRead:
    return WorkMemberRead.model_validate(member)


def serialize_evaluation_report(report: WorkEvaluationReport) -> WorkEvaluationReportRead:
    """member_nameはDBに保存しない派生値（結合先メンバーの現在の名前）のため、
    自動のfrom_attributes変換に頼らず明示的に組み立てる（serialize_work_assignmentと
    同じ方針、CLAUDE.md 保存禁止）。"""
    return WorkEvaluationReportRead(
        id=report.id,
        work_assignment_id=report.work_assignment_id,
        member_id=report.member_id,
        member_name=report.member.name,
        considerations=report.considerations,
        body=report.body,
        generated_at=report.generated_at,
        edited_at=report.edited_at,
    )


def serialize_work_assignment(
    session: Session, work_assignment: WorkAssignment
) -> WorkAssignmentRead:
    """派生値（経過日数・直近記録日・連続記録日数・直近の月次報告有無）を都度算出して
    付与する（CLAUDE.md 保存禁止、データ構造編6.2）。

    membersは無効化済み（is_active=false）も含めて全件返す（一覧画面での「無効化済み」
    表示のため）。評価レポート生成時のメンバー選択候補はフロント側でis_active=trueに
    絞り込む（要件定義書6.11）。
    """
    today = goal_service.resolve_today(session)
    progress = work_service.get_work_assignment_progress(session, work_assignment, today)
    return WorkAssignmentRead(
        id=work_assignment.id,
        goal_id=work_assignment.goal_id,
        client_name=work_assignment.client_name,
        expected_content=work_assignment.expected_content,
        start_date=work_assignment.start_date,
        role=work_assignment.role,
        elapsed_days=progress.elapsed_days,
        last_work_date=progress.last_work_date,
        current_streak=progress.current_streak,
        has_recent_monthly_report=progress.has_recent_monthly_report,
        members=[serialize_work_member(member) for member in work_assignment.members],
    )
