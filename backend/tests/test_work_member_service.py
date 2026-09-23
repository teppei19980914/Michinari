"""work_member_service のテスト（要件定義書6.11「チームメンバー管理」）。

同意ゲート（characteristics保存の都度、consent_confirmed=Trueを要求する）が
サービス層で必ず強制されることを中心に検証する。
"""

import datetime as dt

import pytest

from app.constants.enums import GoalCategory, GoalStatus, WorkMemberGender
from app.models.goal import Goal
from app.models.work import WorkAssignment, WorkEvaluationReport
from app.services import work_member_service
from app.services.exceptions import (
    ConsentRequiredError,
    InvalidStateTransitionError,
    NotFoundError,
    WorkMemberHasEvaluationReportsError,
)


def _make_work_goal(session, status=GoalStatus.ACTIVE):
    goal = Goal(
        category=GoalCategory.WORK, name="仕事目標A", start_date=dt.date(2026, 1, 1), status=status
    )
    session.add(goal)
    session.flush()
    return goal


def _make_work_assignment(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id, expected_content="想定業務内容", start_date=dt.date(2026, 1, 1)
    )
    defaults.update(overrides)
    work_assignment = WorkAssignment(**defaults)
    session.add(work_assignment)
    session.flush()
    return work_assignment


def test_create_member_without_characteristics_needs_no_consent(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)

    member = work_member_service.create_work_member(seeded_session, work_assignment, name="Aさん")

    assert member.characteristics is None
    assert member.consent_confirmed_at is None
    assert member.is_active is True


def test_create_member_with_characteristics_requires_consent(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)

    with pytest.raises(ConsentRequiredError):
        work_member_service.create_work_member(
            seeded_session,
            work_assignment,
            name="Aさん",
            characteristics="明るく前向きな性格",
            consent_confirmed=False,
        )


def test_create_member_with_characteristics_and_consent_succeeds(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)

    member = work_member_service.create_work_member(
        seeded_session,
        work_assignment,
        name="Aさん",
        gender=WorkMemberGender.FEMALE,
        characteristics="明るく前向きな性格",
        consent_confirmed=True,
    )

    assert member.characteristics == "明るく前向きな性格"
    assert member.consent_confirmed_at is not None
    assert member.gender == WorkMemberGender.FEMALE


def test_update_member_reconfirming_same_characteristics_without_consent_fails(seeded_session):
    """値が変わらない再保存でも再確認を要求する（保守的な設計、要件定義書6.11）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    member = work_member_service.create_work_member(
        seeded_session,
        work_assignment,
        name="Aさん",
        characteristics="明るく前向きな性格",
        consent_confirmed=True,
    )

    with pytest.raises(ConsentRequiredError):
        work_member_service.update_work_member(
            seeded_session,
            member,
            characteristics="明るく前向きな性格",
            consent_confirmed=False,
        )


def test_update_member_clearing_characteristics_needs_no_consent(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    member = work_member_service.create_work_member(
        seeded_session,
        work_assignment,
        name="Aさん",
        characteristics="明るく前向きな性格",
        consent_confirmed=True,
    )

    work_member_service.update_work_member(
        seeded_session, member, characteristics=None, consent_confirmed=False
    )

    assert member.characteristics is None
    assert member.consent_confirmed_at is None


def test_update_member_name_only_does_not_touch_characteristics(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    member = work_member_service.create_work_member(
        seeded_session,
        work_assignment,
        name="Aさん",
        characteristics="明るく前向きな性格",
        consent_confirmed=True,
    )
    confirmed_at = member.consent_confirmed_at

    work_member_service.update_work_member(seeded_session, member, name="Bさん")

    assert member.name == "Bさん"
    assert member.characteristics == "明るく前向きな性格"
    assert member.consent_confirmed_at == confirmed_at


def test_update_member_gender(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    member = work_member_service.create_work_member(
        seeded_session, work_assignment, name="Aさん", gender=WorkMemberGender.MALE
    )

    work_member_service.update_work_member(seeded_session, member, gender=WorkMemberGender.OTHER)
    assert member.gender == WorkMemberGender.OTHER

    work_member_service.update_work_member(seeded_session, member, gender=None)
    assert member.gender is None


def test_update_member_on_closed_goal_is_rejected(seeded_session):
    """メンバーが進行中のうちに登録され、後から目標がクローズされた状態を再現する
    （クローズ済みgoalにメンバーを新規作成すること自体はcreate_work_member側で既に
    ensure_goal_editableにより拒否されるため、closeの順序が実運用と逆にならないよう
    ここでは作成後にステータスを書き換える）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    member = work_member_service.create_work_member(seeded_session, work_assignment, name="Aさん")
    goal.status = GoalStatus.CLOSED_WITH_RESULT
    seeded_session.flush()

    with pytest.raises(InvalidStateTransitionError):
        work_member_service.update_work_member(seeded_session, member, name="Bさん")


def test_deactivate_member(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    member = work_member_service.create_work_member(seeded_session, work_assignment, name="Aさん")

    work_member_service.deactivate_work_member(seeded_session, member)

    assert member.is_active is False
    assert work_member_service.list_active_members(work_assignment) == []


def test_delete_member_without_reports_succeeds(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    member = work_member_service.create_work_member(seeded_session, work_assignment, name="Aさん")
    member_id = member.id

    work_member_service.delete_work_member(seeded_session, member)

    with pytest.raises(NotFoundError):
        work_member_service.get_member(seeded_session, member_id)


def test_delete_member_with_reports_is_rejected(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    member = work_member_service.create_work_member(seeded_session, work_assignment, name="Aさん")
    seeded_session.add(
        WorkEvaluationReport(
            work_assignment_id=work_assignment.id,
            member_id=member.id,
            considerations="考慮事項",
            body="レポート本文",
            generated_at=dt.datetime(2026, 1, 1),
        )
    )
    seeded_session.flush()

    with pytest.raises(WorkMemberHasEvaluationReportsError):
        work_member_service.delete_work_member(seeded_session, member)


def test_get_member_not_found(seeded_session):
    with pytest.raises(NotFoundError):
        work_member_service.get_member(seeded_session, 999999)
