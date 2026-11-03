"""節目のお祝いAPIのテスト（開発Todo_節目のお祝い_v1.0 §3.3 B-12・B-14）。

準備はサービス層（milestone_service_common）・直接のモデル生成で行い、APIの応答・
認可境界（他目標の節目IDの指定）・エラー変換を見る。
"""

import datetime as dt

from app.constants.enums import GoalCategory, GoalStatus, MilestoneType
from app.models.goal import Goal
from app.models.milestone import GoalMilestoneAchievement


def _make_goal(session, *, name="節目API検証") -> Goal:
    goal = Goal(
        name=name,
        category=GoalCategory.EXAM,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_achievement(session, goal_id, *, key="3", celebrated_at=None) -> GoalMilestoneAchievement:
    row = GoalMilestoneAchievement(
        goal_id=goal_id,
        milestone_type=MilestoneType.CONSECUTIVE_DAYS,
        milestone_key=key,
        achieved_at=dt.datetime(2026, 1, 1),
        celebrated_at=celebrated_at,
    )
    session.add(row)
    session.flush()
    return row


def test_list_milestones_returns_all_achievements(seeded_session, client):
    goal = _make_goal(seeded_session)
    _make_achievement(seeded_session, goal.id, key="3", celebrated_at=dt.datetime(2026, 1, 1))
    _make_achievement(seeded_session, goal.id, key="7")

    response = client.get(f"/api/v1/goals/{goal.id}/milestones")

    assert response.status_code == 200, response.text
    assert {row["milestone_key"] for row in response.json()} == {"3", "7"}


def test_list_milestones_unknown_goal_returns_404(client):
    response = client.get("/api/v1/goals/999999/milestones")
    assert response.status_code == 404


def test_pending_celebrations_excludes_already_celebrated(seeded_session, client):
    goal = _make_goal(seeded_session)
    _make_achievement(seeded_session, goal.id, key="3", celebrated_at=dt.datetime(2026, 1, 1))
    _make_achievement(seeded_session, goal.id, key="7")

    response = client.get(f"/api/v1/goals/{goal.id}/milestones/pending-celebrations")

    assert response.status_code == 200, response.text
    assert [row["milestone_key"] for row in response.json()] == ["7"]


def test_pending_celebrations_unknown_goal_returns_404(client):
    response = client.get("/api/v1/goals/999999/milestones/pending-celebrations")
    assert response.status_code == 404


def test_celebrate_marks_timestamp(seeded_session, client):
    goal = _make_goal(seeded_session)
    row = _make_achievement(seeded_session, goal.id, key="3")

    response = client.post(f"/api/v1/goals/{goal.id}/milestones/{row.id}/celebrate")

    assert response.status_code == 200, response.text
    assert response.json()["celebrated_at"] is not None


def test_celebrate_rejects_milestone_belonging_to_another_goal(seeded_session, client):
    goal = _make_goal(seeded_session, name="目標A")
    other_goal = _make_goal(seeded_session, name="目標B")
    row = _make_achievement(seeded_session, other_goal.id, key="3")

    response = client.post(f"/api/v1/goals/{goal.id}/milestones/{row.id}/celebrate")

    assert response.status_code == 404


def test_celebrate_unknown_milestone_returns_404(seeded_session, client):
    goal = _make_goal(seeded_session)

    response = client.post(f"/api/v1/goals/{goal.id}/milestones/999999/celebrate")

    assert response.status_code == 404


def test_celebrate_unknown_goal_returns_404(client):
    response = client.post("/api/v1/goals/999999/milestones/1/celebrate")
    assert response.status_code == 404
