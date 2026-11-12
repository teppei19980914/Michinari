"""ふりかえりまとめ・共有カードAPIのテスト（開発Todo「まとめと共有カード」v1.0 §3.2・§3.4）。

匿名化対象情報（日記本文等）がレスポンスに含まれないことを確認する（受け入れ基準、
要件定義書R-157）。AI一文生成はapp.ai.clientの通信関数を差し替えて検証する。
"""

import datetime as dt

from app.ai import client as ai_client
from app.constants.enums import GoalCategory, GoalStatus
from app.models.goal import Goal
from app.models.record import DailyGoalDiary, DailyRecord
from tests.ai_chat_fakes import FakeAi


def _make_goal(session, *, name="共有カードAPI検証") -> Goal:
    goal = Goal(
        name=name,
        category=GoalCategory.EXAM,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    return goal


def test_get_summary_card_returns_aggregate_and_excludes_diary_body(seeded_session, client):
    goal = _make_goal(seeded_session)
    record = DailyRecord(record_date=dt.date(2026, 1, 5), exam_record_state="REPORTED")
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        DailyGoalDiary(
            daily_record_id=record.id,
            goal_id=goal.id,
            diary_body="伏せておきたい個人的な事情の本文",
            diary_learned="学んだこと",
        )
    )
    seeded_session.commit()

    response = client.get(
        f"/api/v1/goals/{goal.id}/summary-card",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record_days"] == 1
    assert "伏せておきたい個人的な事情の本文" not in response.text
    assert "学んだこと" not in response.text


def test_get_summary_card_unknown_goal_returns_404(client):
    response = client.get(
        "/api/v1/goals/999999/summary-card",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
    )
    assert response.status_code == 404


def test_get_summary_card_rejects_from_after_to(seeded_session, client):
    goal = _make_goal(seeded_session)

    response = client.get(
        f"/api/v1/goals/{goal.id}/summary-card",
        params={"date_from": "2026-01-31", "date_to": "2026-01-01"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_generate_summary_card_sentence_returns_generated_text(seeded_session, client, monkeypatch):
    goal = _make_goal(seeded_session)
    FakeAi(monkeypatch, ("積み重ねた努力が伝わる一文です。",))

    response = client.post(
        f"/api/v1/goals/{goal.id}/summary-card/sentence",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"sentence": "積み重ねた努力が伝わる一文です。"}


def test_generate_summary_card_sentence_requires_ai_connection(seeded_session, client, monkeypatch):
    monkeypatch.setattr(ai_client, "is_authenticated", lambda session: False)
    goal = _make_goal(seeded_session)

    response = client.post(
        f"/api/v1/goals/{goal.id}/summary-card/sentence",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AI_AUTH_REQUIRED"
