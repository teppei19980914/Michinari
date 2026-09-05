"""案件情報のAPI補助（データ構造編6.2、実装フェーズ分割計画書Phase21）。

serialize_work_assignment は goals.py（目標詳細への案件情報ネスト表示、および
案件情報作成・更新エンドポイントの応答組み立て）から使う共通処理（CLAUDE.md DRYの原則、
api/books.pyのserialize_bookと同じ位置づけ）。案件情報の作成・更新は書籍と異なり、
目標配下のネストパス（POST/PATCH /goals/{id}/work-assignment）に統一するため、
bookのような独立リソースパス用のルーターはここには置かない（データ構造編6.2）。
"""

from sqlalchemy.orm import Session

from app.models.work import WorkAssignment
from app.schemas.work import WorkAssignmentRead
from app.services import goal_service, work_service


def serialize_work_assignment(
    session: Session, work_assignment: WorkAssignment
) -> WorkAssignmentRead:
    """派生値（経過日数・直近記録日・連続記録日数・直近の月次報告有無）を都度算出して
    付与する（CLAUDE.md 保存禁止、データ構造編6.2）。"""
    today = goal_service.resolve_today(session)
    progress = work_service.get_work_assignment_progress(session, work_assignment, today)
    return WorkAssignmentRead(
        id=work_assignment.id,
        goal_id=work_assignment.goal_id,
        client_name=work_assignment.client_name,
        expected_content=work_assignment.expected_content,
        start_date=work_assignment.start_date,
        elapsed_days=progress.elapsed_days,
        last_work_date=progress.last_work_date,
        current_streak=progress.current_streak,
        has_recent_monthly_report=progress.has_recent_monthly_report,
    )
