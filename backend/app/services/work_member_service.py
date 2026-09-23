"""チームメンバーのCRUD（要件定義書6.11「チームメンバー管理」）。

work_assignmentの子（book/materialがgoalの子であるのと同じ位置づけ）。characteristics
（特徴・性格）は本アプリ初の第三者PIIフィールドであり、本人確認済みボタンのクリックを
サーバ側で必ず検証する（同意ゲート、要件定義書6.11「登録時に本人確認済みであることを
利用者に確認させる」）。フロント側のチェックボックス無効化はUXの補助に過ぎず、
生のAPI呼び出しからも保護できるようここで強制する。
"""

from sqlalchemy.orm import Session

from app.constants.enums import WorkMemberGender
from app.constants.sentinels import UNSET
from app.models.base import utcnow
from app.models.work import WorkAssignment, WorkEvaluationReport, WorkMember
from app.services import goal_service
from app.services.exceptions import (
    ConsentRequiredError,
    NotFoundError,
    WorkMemberHasEvaluationReportsError,
)


def get_member(session: Session, member_id: int) -> WorkMember:
    member = session.get(WorkMember, member_id)
    if member is None:
        raise NotFoundError("メンバー", member_id)
    return member


def list_active_members(work_assignment: WorkAssignment) -> list[WorkMember]:
    """work_assignment配下の有効なメンバー一覧を返す（is_active=trueのみ、
    material_service.list_active_materialsと同じ方針）。"""
    return [member for member in work_assignment.members if member.is_active]


def _apply_characteristics(
    member: WorkMember, *, characteristics: str | None, consent_confirmed: bool
) -> None:
    """characteristicsを非空にする保存の都度、同意確認を要求する（値が変わらない
    再保存でも再確認を要求する保守的な設計。第三者PIIを扱う初のフィールドであるため）。
    空文字/Noneに戻す場合は同意不要で、consent_confirmed_atもNULLへ戻す
    （存在しない内容に対する確認済み表示を残さないため）。
    """
    if characteristics:
        if not consent_confirmed:
            raise ConsentRequiredError()
        member.characteristics = characteristics
        member.consent_confirmed_at = utcnow()
    else:
        member.characteristics = None
        member.consent_confirmed_at = None


def create_work_member(
    session: Session,
    work_assignment: WorkAssignment,
    *,
    name: str,
    gender: WorkMemberGender | None = None,
    characteristics: str | None = None,
    consent_confirmed: bool = False,
) -> WorkMember:
    goal_service.ensure_goal_editable(work_assignment.goal)

    member = WorkMember(work_assignment_id=work_assignment.id, name=name, gender=gender)
    _apply_characteristics(
        member, characteristics=characteristics, consent_confirmed=consent_confirmed
    )
    session.add(member)
    session.flush()
    return member


def update_work_member(
    session: Session,
    member: WorkMember,
    *,
    name: str | None = None,
    gender: WorkMemberGender | None = UNSET,
    characteristics: str | None = UNSET,
    consent_confirmed: bool = False,
) -> WorkMember:
    goal_service.ensure_goal_editable(member.work_assignment.goal)

    if name is not None:
        member.name = name
    if gender is not UNSET:
        member.gender = gender
    if characteristics is not UNSET:
        _apply_characteristics(
            member, characteristics=characteristics, consent_confirmed=consent_confirmed
        )

    session.flush()
    return member


def deactivate_work_member(session: Session, member: WorkMember) -> WorkMember:
    goal_service.ensure_goal_editable(member.work_assignment.goal)
    member.is_active = False
    session.flush()
    return member


def delete_work_member(session: Session, member: WorkMember) -> None:
    """評価レポートが存在するメンバーの物理削除は拒否する（データ構造編6.2相当。
    MaterialHasStudyLogsErrorと同型）。"""
    goal_service.ensure_goal_editable(member.work_assignment.goal)
    has_reports = (
        session.query(WorkEvaluationReport.id)
        .filter(WorkEvaluationReport.member_id == member.id)
        .first()
        is not None
    )
    if has_reports:
        raise WorkMemberHasEvaluationReportsError(member.id)
    session.delete(member)
    session.flush()
