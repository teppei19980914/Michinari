"""目標相談チャットの相談履歴（保存・一覧・削除）のテスト（S10、開発Todo v1.1 V6〜V8）。"""

import datetime as dt

import pytest

from app.constants.enums import GoalConsultationAnswerStatus
from app.models.goal import GoalConsultationLog
from app.services import goal_consultation_log_service as service
from app.services.exceptions import NotFoundError
from tests.ai_context_helpers import make_goal

_DATE_A = dt.date(2026, 1, 10)
_DATE_B = dt.date(2026, 1, 17)
_WEEK = (dt.date(2026, 1, 5), dt.date(2026, 1, 11))


def test_save_answered_entry_round_trips_citations(seeded_session):
    goal = make_goal(seeded_session)

    service.save(
        seeded_session,
        goal=goal,
        question="この後何を勉強すべき？",
        answer_status=GoalConsultationAnswerStatus.ANSWERED,
        answer_body="順調です。",
        cited_dates=(_DATE_A, _DATE_B),
        cited_weeks=(_WEEK,),
    )

    [entry] = service.list_for_goal(seeded_session, goal)
    assert entry.question == "この後何を勉強すべき？"
    assert entry.answer_status is GoalConsultationAnswerStatus.ANSWERED
    assert entry.answer_body == "順調です。"
    assert entry.cited_dates == (_DATE_A, _DATE_B)
    assert entry.cited_weeks == (_WEEK,)


def test_save_unavailable_entry_has_empty_citations(seeded_session):
    goal = make_goal(seeded_session)

    service.save(
        seeded_session,
        goal=goal,
        question="禁止語を含む質問",
        answer_status=GoalConsultationAnswerStatus.UNAVAILABLE,
        answer_body="",
        cited_dates=(),
        cited_weeks=(),
    )

    [entry] = service.list_for_goal(seeded_session, goal)
    assert entry.answer_status is GoalConsultationAnswerStatus.UNAVAILABLE
    assert entry.answer_body == ""
    assert entry.cited_dates == ()
    assert entry.cited_weeks == ()


def test_list_for_goal_orders_by_created_at_then_id(seeded_session):
    """同一created_atでもid昇順でタイブレークする（CODING_RULES.md「タイムスタンプでの
    並び替え」）。"""
    goal = make_goal(seeded_session)
    for index in range(3):
        service.save(
            seeded_session,
            goal=goal,
            question=f"質問{index}",
            answer_status=GoalConsultationAnswerStatus.ANSWERED,
            answer_body=f"回答{index}",
            cited_dates=(),
            cited_weeks=(),
        )
    rows = seeded_session.query(GoalConsultationLog).filter_by(goal_id=goal.id).all()
    same_time = rows[0].created_at
    for row in rows:
        row.created_at = same_time
    seeded_session.commit()

    entries = service.list_for_goal(seeded_session, goal)

    assert [entry.question for entry in entries] == ["質問0", "質問1", "質問2"]


def test_list_for_goal_excludes_other_goals(seeded_session):
    goal_a = make_goal(seeded_session, name="目標A")
    goal_b = make_goal(seeded_session, name="目標B")
    service.save(
        seeded_session,
        goal=goal_a,
        question="目標Aの質問",
        answer_status=GoalConsultationAnswerStatus.ANSWERED,
        answer_body="回答",
        cited_dates=(),
        cited_weeks=(),
    )
    service.save(
        seeded_session,
        goal=goal_b,
        question="目標Bの質問",
        answer_status=GoalConsultationAnswerStatus.ANSWERED,
        answer_body="回答",
        cited_dates=(),
        cited_weeks=(),
    )

    entries = service.list_for_goal(seeded_session, goal_a)

    assert [entry.question for entry in entries] == ["目標Aの質問"]


def test_delete_removes_the_entry(seeded_session):
    goal = make_goal(seeded_session)
    service.save(
        seeded_session,
        goal=goal,
        question="質問",
        answer_status=GoalConsultationAnswerStatus.ANSWERED,
        answer_body="回答",
        cited_dates=(),
        cited_weeks=(),
    )
    [entry] = service.list_for_goal(seeded_session, goal)

    service.delete(seeded_session, goal, entry.id)

    assert service.list_for_goal(seeded_session, goal) == []


def test_delete_rejects_log_id_belonging_to_another_goal(seeded_session):
    """他目標の履歴は、goal_idが一致しないため削除できない（認可境界、開発Todo v1.1 §5）。"""
    goal_a = make_goal(seeded_session, name="目標A")
    goal_b = make_goal(seeded_session, name="目標B")
    service.save(
        seeded_session,
        goal=goal_a,
        question="目標Aの質問",
        answer_status=GoalConsultationAnswerStatus.ANSWERED,
        answer_body="回答",
        cited_dates=(),
        cited_weeks=(),
    )
    [entry] = service.list_for_goal(seeded_session, goal_a)

    with pytest.raises(NotFoundError):
        service.delete(seeded_session, goal_b, entry.id)


def test_delete_rejects_unknown_log_id(seeded_session):
    goal = make_goal(seeded_session)

    with pytest.raises(NotFoundError):
        service.delete(seeded_session, goal, 999999)


def test_log_is_cascade_deleted_with_goal(seeded_session):
    goal = make_goal(seeded_session)
    service.save(
        seeded_session,
        goal=goal,
        question="質問",
        answer_status=GoalConsultationAnswerStatus.ANSWERED,
        answer_body="回答",
        cited_dates=(),
        cited_weeks=(),
    )

    seeded_session.delete(goal)
    seeded_session.commit()

    assert seeded_session.query(GoalConsultationLog).count() == 0
