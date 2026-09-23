"""AI評価レポートAPIのテスト（要件定義書6.11）。

月次報告・半期評価APIのテスト（test_api_work_report.py）と同じ方針で、
app.ai.client.send_message をモックする。
"""

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _stub_send_message(monkeypatch, *, response="評価レポート本文"):
    monkeypatch.setattr(
        ai_client,
        "send_message",
        lambda session, *, chat_uid, message: ai_client.SendResult(
            response_text=response, latency_ms=5
        ),
    )
    counter = iter(range(1000))
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: f"chat-{next(counter)}",
    )


def _create_evaluator_work_goal_with_member(client, start_date="2026-01-01"):
    goal = client.post(
        "/api/v1/goals", json={"category": "WORK", "name": "仕事目標A", "start_date": start_date}
    ).json()
    client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment",
        json={"expected_content": "想定業務内容", "start_date": start_date},
    )
    client.patch(f"/api/v1/goals/{goal['id']}/work-assignment", json={"role": "EVALUATOR"})
    member = client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment/members", json={"name": "Aさん"}
    ).json()
    return goal, member


def test_generate_evaluation_report_succeeds(client, monkeypatch):
    _stub_send_message(monkeypatch, response="生成された評価レポート")
    goal, member = _create_evaluator_work_goal_with_member(client)

    response = client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment/evaluation-reports",
        json={"member_id": member["id"], "considerations": "納期意識を評価してほしい"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["body"] == "生成された評価レポート"
    assert body["member_id"] == member["id"]
    assert body["member_name"] == "Aさん"
    assert body["edited_at"] is None


def test_generate_evaluation_report_rejects_non_evaluator_role(client, monkeypatch):
    _stub_send_message(monkeypatch)
    goal, member = _create_evaluator_work_goal_with_member(client)
    client.patch(f"/api/v1/goals/{goal['id']}/work-assignment", json={"role": "EVALUATEE"})

    response = client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment/evaluation-reports",
        json={"member_id": member["id"], "considerations": "考慮事項"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_generate_evaluation_report_without_work_assignment_returns_404(client):
    goal = client.post(
        "/api/v1/goals", json={"category": "WORK", "name": "仕事目標A", "start_date": "2026-01-01"}
    ).json()

    response = client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment/evaluation-reports",
        json={"member_id": 1, "considerations": "考慮事項"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_list_evaluation_reports_orders_newest_first(client, monkeypatch):
    _stub_send_message(monkeypatch, response="1回目")
    goal, member = _create_evaluator_work_goal_with_member(client)
    client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment/evaluation-reports",
        json={"member_id": member["id"], "considerations": "考慮事項1"},
    )
    _stub_send_message(monkeypatch, response="2回目")
    client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment/evaluation-reports",
        json={"member_id": member["id"], "considerations": "考慮事項2"},
    )

    response = client.get(f"/api/v1/goals/{goal['id']}/work-assignment/evaluation-reports")

    assert response.status_code == 200, response.text
    bodies = [r["body"] for r in response.json()]
    assert bodies == ["2回目", "1回目"]


def test_update_evaluation_report_sets_edited_at(client, monkeypatch):
    _stub_send_message(monkeypatch)
    goal, member = _create_evaluator_work_goal_with_member(client)
    report = client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment/evaluation-reports",
        json={"member_id": member["id"], "considerations": "考慮事項"},
    ).json()

    response = client.patch(
        f"/api/v1/goals/{goal['id']}/work-assignment/evaluation-reports/{report['id']}",
        json={"body": "人が修正した本文"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["body"] == "人が修正した本文"
    assert body["edited_at"] is not None
