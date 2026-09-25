"""work_evaluation_service のテスト（要件定義書6.11「AI評価レポート」）。

work_feedback_service.py・work_report_service.py のテストと同じ方針で、
app.ai.client.send_message をモックして実際のAI基盤へは接続しない。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.constants.enums import GoalCategory, GoalStatus, WorkEvaluationRole
from app.models.ai import AiConversation
from app.models.goal import Goal
from app.models.record import ChatMessage, DailyRecord
from app.models.work import WorkAssignment, WorkEvaluationReport
from app.services import work_evaluation_service, work_member_service
from app.services.exceptions import ValidationError


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _cleanup_committed_rows(seeded_session):
    """AI呼び出し失敗時にcommitされる行が他テストへ漏れないよう明示的に空にする
    （test_work_feedback_service.pyと同じ後始末パターン）。"""
    yield
    from app.models.base import Base

    seeded_session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        seeded_session.execute(table.delete())
    seeded_session.commit()


def _make_work_goal(session, role=WorkEvaluationRole.EVALUATOR):
    goal = Goal(
        category=GoalCategory.WORK,
        name="仕事目標A",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    work_assignment = WorkAssignment(
        goal_id=goal.id,
        expected_content="想定業務内容",
        start_date=dt.date(2026, 1, 1),
        role=role,
    )
    session.add(work_assignment)
    session.flush()
    return goal, work_assignment


def _stub_send_message(monkeypatch, *, response="評価レポート本文"):
    calls = []

    def _fake(session, *, chat_uid, message):
        calls.append({"chat_uid": chat_uid, "message": message})
        return ai_client.SendResult(response_text=response, latency_ms=123)

    monkeypatch.setattr(ai_client, "send_message", _fake)
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: "chat-uid-eval",
    )
    return calls


def test_generate_evaluation_report_requires_evaluator_role(seeded_session, monkeypatch):
    _stub_send_message(monkeypatch)
    goal, work_assignment = _make_work_goal(seeded_session, role=WorkEvaluationRole.EVALUATEE)
    member = work_member_service.create_work_member(seeded_session, work_assignment, name="Aさん")

    with pytest.raises(ValidationError):
        work_evaluation_service.generate_evaluation_report(
            seeded_session,
            work_assignment,
            member=member,
            considerations="考慮事項",
            today=dt.date(2026, 2, 1),
        )


def test_generate_evaluation_report_requires_evaluator_role_when_unset(seeded_session, monkeypatch):
    _stub_send_message(monkeypatch)
    goal, work_assignment = _make_work_goal(seeded_session, role=None)
    member = work_member_service.create_work_member(seeded_session, work_assignment, name="Aさん")

    with pytest.raises(ValidationError):
        work_evaluation_service.generate_evaluation_report(
            seeded_session,
            work_assignment,
            member=member,
            considerations="考慮事項",
            today=dt.date(2026, 2, 1),
        )


def test_generate_evaluation_report_rejects_member_from_other_assignment(
    seeded_session, monkeypatch
):
    _stub_send_message(monkeypatch)
    _, work_assignment_a = _make_work_goal(seeded_session)
    _, work_assignment_b = _make_work_goal(seeded_session)
    other_member = work_member_service.create_work_member(
        seeded_session, work_assignment_b, name="Bさん"
    )

    with pytest.raises(ValidationError):
        work_evaluation_service.generate_evaluation_report(
            seeded_session,
            work_assignment_a,
            member=other_member,
            considerations="考慮事項",
            today=dt.date(2026, 2, 1),
        )


def test_generate_evaluation_report_succeeds_and_persists(seeded_session, monkeypatch):
    calls = _stub_send_message(monkeypatch, response="生成された評価レポート")
    goal, work_assignment = _make_work_goal(seeded_session)
    from app.constants.enums import WorkMemberGender

    member = work_member_service.create_work_member(
        seeded_session,
        work_assignment,
        name="Aさん",
        gender=WorkMemberGender.FEMALE,
        characteristics="粘り強い性格",
        consent_confirmed=True,
    )

    report = work_evaluation_service.generate_evaluation_report(
        seeded_session,
        work_assignment,
        member=member,
        considerations="納期意識を評価してほしい",
        today=dt.date(2026, 2, 1),
    )

    assert report.body == "生成された評価レポート"
    assert report.member_id == member.id
    assert report.work_assignment_id == work_assignment.id
    assert report.considerations == "納期意識を評価してほしい"
    assert report.edited_at is None
    assert len(calls) == 1
    # プロンプトにメンバーの性別・特徴・考慮事項が注入されていること。
    assert "女性" in calls[0]["message"]
    assert "粘り強い性格" in calls[0]["message"]
    assert "納期意識を評価してほしい" in calls[0]["message"]

    conversation = (
        seeded_session.query(AiConversation)
        .filter_by(goal_id=goal.id, scope_key=str(member.id))
        .one()
    )
    assert conversation.conversation_uid == "chat-uid-eval"


def test_generate_evaluation_report_includes_past_feedback_history(seeded_session, monkeypatch):
    calls = _stub_send_message(monkeypatch)
    goal, work_assignment = _make_work_goal(seeded_session)
    member = work_member_service.create_work_member(seeded_session, work_assignment, name="Aさん")

    from app.constants.enums import AiPurpose, ChatRole

    record = DailyRecord(record_date=dt.date(2026, 1, 15))
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        ChatMessage(
            daily_record_id=record.id,
            goal_id=goal.id,
            purpose=AiPurpose.DAILY_FEEDBACK_WORK,
            role=ChatRole.ASSISTANT,
            content="過去のNewtonXフィードバック本文",
            sequence=1,
        )
    )
    seeded_session.flush()

    work_evaluation_service.generate_evaluation_report(
        seeded_session,
        work_assignment,
        member=member,
        considerations="考慮事項",
        today=dt.date(2026, 2, 1),
    )

    assert "過去のNewtonXフィードバック本文" in calls[0]["message"]


def test_generate_evaluation_report_is_append_only_across_regenerations(
    seeded_session, monkeypatch
):
    _stub_send_message(monkeypatch, response="1回目")
    goal, work_assignment = _make_work_goal(seeded_session)
    member = work_member_service.create_work_member(seeded_session, work_assignment, name="Aさん")

    first = work_evaluation_service.generate_evaluation_report(
        seeded_session,
        work_assignment,
        member=member,
        considerations="考慮事項1",
        today=dt.date(2026, 2, 1),
    )

    _stub_send_message(monkeypatch, response="2回目")
    second = work_evaluation_service.generate_evaluation_report(
        seeded_session,
        work_assignment,
        member=member,
        considerations="考慮事項2",
        today=dt.date(2026, 3, 1),
    )

    assert first.id != second.id
    reports = work_evaluation_service.list_evaluation_reports(seeded_session, work_assignment)
    assert [r.id for r in reports] == [second.id, first.id]


def test_list_evaluation_reports_breaks_generated_at_ties_by_id(seeded_session):
    """generated_at が同一マイクロ秒に丸まった場合でも、より新しく生成された行（idが大きい
    方）を先頭にすること。utcnow()はマイクロ秒精度だが、短時間での連続生成では実測で
    同一値に丸まることを確認済みの回帰テスト（元は
    test_generate_evaluation_report_is_append_only_across_regenerationsがタイミング
    依存で間欠的に失敗する形で発覚した）。ORDER BYがgenerated_at単独だとSQLiteの
    タイブレークが不定になり、再生成直後の一覧で新しい版が末尾に来ることがあった。"""
    goal, work_assignment = _make_work_goal(seeded_session)
    member = work_member_service.create_work_member(seeded_session, work_assignment, name="Aさん")
    tied_timestamp = dt.datetime(2026, 2, 1, 12, 0, 0, 123456, tzinfo=dt.UTC)
    older = WorkEvaluationReport(
        work_assignment_id=work_assignment.id,
        member_id=member.id,
        considerations="考慮事項1",
        body="1回目",
        generated_at=tied_timestamp,
    )
    seeded_session.add(older)
    seeded_session.flush()
    newer = WorkEvaluationReport(
        work_assignment_id=work_assignment.id,
        member_id=member.id,
        considerations="考慮事項2",
        body="2回目",
        generated_at=tied_timestamp,
    )
    seeded_session.add(newer)
    seeded_session.flush()
    assert older.id < newer.id

    reports = work_evaluation_service.list_evaluation_reports(seeded_session, work_assignment)

    assert [r.id for r in reports] == [newer.id, older.id]


def test_get_evaluation_report_raises_not_found(seeded_session):
    from app.services.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        work_evaluation_service.get_evaluation_report(seeded_session, 999999)


def test_update_evaluation_report_sets_edited_at(seeded_session, monkeypatch):
    _stub_send_message(monkeypatch)
    goal, work_assignment = _make_work_goal(seeded_session)
    member = work_member_service.create_work_member(seeded_session, work_assignment, name="Aさん")
    report = work_evaluation_service.generate_evaluation_report(
        seeded_session,
        work_assignment,
        member=member,
        considerations="考慮事項",
        today=dt.date(2026, 2, 1),
    )
    assert report.edited_at is None

    work_evaluation_service.update_evaluation_report(
        seeded_session, report, body="人が修正した本文"
    )

    assert report.body == "人が修正した本文"
    assert report.edited_at is not None


def test_list_evaluation_reports_filters_by_member(seeded_session, monkeypatch):
    _stub_send_message(monkeypatch)
    goal, work_assignment = _make_work_goal(seeded_session)
    member_a = work_member_service.create_work_member(seeded_session, work_assignment, name="Aさん")
    member_b = work_member_service.create_work_member(seeded_session, work_assignment, name="Bさん")
    work_evaluation_service.generate_evaluation_report(
        seeded_session,
        work_assignment,
        member=member_a,
        considerations="考慮事項A",
        today=dt.date(2026, 2, 1),
    )
    work_evaluation_service.generate_evaluation_report(
        seeded_session,
        work_assignment,
        member=member_b,
        considerations="考慮事項B",
        today=dt.date(2026, 2, 1),
    )

    reports_for_a = work_evaluation_service.list_evaluation_reports(
        seeded_session, work_assignment, member_id=member_a.id
    )

    assert len(reports_for_a) == 1
    assert reports_for_a[0].member_id == member_a.id
