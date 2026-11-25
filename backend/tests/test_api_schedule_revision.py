"""AIによるスケジュール修正案のAPIテスト（開発Todo_スケジュール・ガントチャート_v1.1
13.7・13.10、単位5）。

検証ルールの分岐・AI呼び出し自体はtest_schedule_revision_service.pyで検証済みのため、
ここではAPI層の配線（ステータスコード・エラーコード・認可境界）を中心に確認する。
実際のAI基盤へは接続せず、`tests.ai_chat_fakes.FakeAi`で差し替える。
"""

import pytest

from app.ai import rate_limiter
from tests.ai_chat_fakes import FakeAi

_TODAY_ISO = "2026-11-25"


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _create_goal(client, name: str = "目標A") -> dict:
    return client.post("/api/v1/goals", json={"name": name, "start_date": "2026-01-01"}).json()


def _create_item(client, goal_id: int, *, start: str, end: str) -> dict:
    response = client.put(
        f"/api/v1/goals/{goal_id}/schedule",
        json={
            "revision": 0,
            "items": [
                {
                    "title": "作業項目A",
                    "planned_start_date": start,
                    "planned_end_date": end,
                    "status": "NOT_STARTED",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["items"][0]


def _change_block(item_id: int, start: str, end: str, reason: str = "遅れています") -> str:
    return f"種類: 変更\n行ID: {item_id}\n予定開始日: {start}\n予定終了日: {end}\n理由: {reason}"


def test_generate_endpoint_returns_a_proposal_for_manual_trigger(client, monkeypatch):
    goal = _create_goal(client)
    item = _create_item(client, goal["id"], start="2026-12-01", end="2026-12-10")
    FakeAi(monkeypatch, (_change_block(item["id"], "2026-12-05", "2026-12-15"),))

    response = client.post(
        f"/api/v1/goals/{goal['id']}/schedule/revision-proposals",
        json={"trigger": "MANUAL"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["proposal"] is not None
    assert body["proposal"]["status"] == "PENDING"
    assert body["proposal"]["items"][0]["is_stale"] is False
    assert body["proposal"]["items"][0]["proposed_planned_start_date"] == "2026-12-05"


def test_generate_endpoint_requires_record_date_for_auto_trigger(client):
    goal = _create_goal(client)
    _create_item(client, goal["id"], start="2026-01-01", end="2026-01-05")

    response = client.post(
        f"/api/v1/goals/{goal['id']}/schedule/revision-proposals",
        json={"trigger": "AUTO"},
    )

    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_generate_endpoint_returns_null_proposal_when_auto_has_no_delay(client, monkeypatch):
    goal = _create_goal(client)
    _create_item(client, goal["id"], start="2026-12-01", end="2026-12-10")
    fake = FakeAi(monkeypatch, ("総評: 対象なし",))

    response = client.post(
        f"/api/v1/goals/{goal['id']}/schedule/revision-proposals",
        json={"trigger": "AUTO", "record_date": _TODAY_ISO},
    )

    assert response.status_code == 200, response.text
    assert response.json()["proposal"] is None
    assert fake.sent == []


def test_decide_endpoint_approves_a_change_and_bumps_the_revision(client, monkeypatch):
    goal = _create_goal(client)
    item = _create_item(client, goal["id"], start="2026-12-01", end="2026-12-10")
    FakeAi(monkeypatch, (_change_block(item["id"], "2026-12-05", "2026-12-15"),))
    generated = client.post(
        f"/api/v1/goals/{goal['id']}/schedule/revision-proposals",
        json={"trigger": "MANUAL"},
    ).json()
    proposal_id = generated["proposal"]["id"]
    proposal_item_id = generated["proposal"]["items"][0]["id"]

    response = client.post(
        f"/api/v1/goals/{goal['id']}/schedule/revision-proposals/{proposal_id}/decisions",
        json={"decisions": [{"proposal_item_id": proposal_item_id, "decision": "APPROVED"}]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcomes"] == [
        {"proposal_item_id": proposal_item_id, "applied": True, "blocked_reason": None}
    ]
    assert body["proposal"]["status"] == "RESOLVED"

    schedule = client.get(f"/api/v1/goals/{goal['id']}/schedule").json()
    assert schedule["items"][0]["planned_start_date"] == "2026-12-05"
    assert schedule["items"][0]["planned_end_date"] == "2026-12-15"
    assert schedule["revision"] == 2  # 保存(1)→承認(2)


def test_decide_endpoint_marks_a_stale_row_without_applying_it(client, monkeypatch):
    goal = _create_goal(client)
    item = _create_item(client, goal["id"], start="2026-12-01", end="2026-12-10")
    FakeAi(monkeypatch, (_change_block(item["id"], "2026-12-05", "2026-12-15"),))
    generated = client.post(
        f"/api/v1/goals/{goal['id']}/schedule/revision-proposals",
        json={"trigger": "MANUAL"},
    ).json()
    proposal_id = generated["proposal"]["id"]
    proposal_item_id = generated["proposal"]["items"][0]["id"]

    # スケジュール画面で既に編集済み（before値と現在値が一致しない状態、D-59）。
    client.put(
        f"/api/v1/goals/{goal['id']}/schedule",
        json={
            "revision": 1,
            "items": [
                {
                    "id": item["id"],
                    "title": "作業項目A",
                    "planned_start_date": "2026-12-01",
                    "planned_end_date": "2026-12-20",
                    "status": "NOT_STARTED",
                }
            ],
        },
    )

    response = client.post(
        f"/api/v1/goals/{goal['id']}/schedule/revision-proposals/{proposal_id}/decisions",
        json={"decisions": [{"proposal_item_id": proposal_item_id, "decision": "APPROVED"}]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcomes"] == [
        {
            "proposal_item_id": proposal_item_id,
            "applied": False,
            "blocked_reason": "STALE_BEFORE_VALUE",
        }
    ]
    assert body["proposal"]["items"][0]["decision"] == "PENDING"
    assert body["proposal"]["items"][0]["is_stale"] is True
    assert body["proposal"]["status"] == "PENDING"


def test_decide_endpoint_rejects_a_proposal_that_is_not_pending(client, monkeypatch):
    goal = _create_goal(client)
    item = _create_item(client, goal["id"], start="2026-12-01", end="2026-12-10")
    FakeAi(monkeypatch, (_change_block(item["id"], "2026-12-05", "2026-12-15"),))
    generated = client.post(
        f"/api/v1/goals/{goal['id']}/schedule/revision-proposals",
        json={"trigger": "MANUAL"},
    ).json()
    proposal_id = generated["proposal"]["id"]
    proposal_item_id = generated["proposal"]["items"][0]["id"]
    client.post(
        f"/api/v1/goals/{goal['id']}/schedule/revision-proposals/{proposal_id}/decisions",
        json={"decisions": [{"proposal_item_id": proposal_item_id, "decision": "REJECTED"}]},
    )

    response = client.post(
        f"/api/v1/goals/{goal['id']}/schedule/revision-proposals/{proposal_id}/decisions",
        json={"decisions": [{"proposal_item_id": proposal_item_id, "decision": "APPROVED"}]},
    )

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "SCHEDULE_REVISION_PROPOSAL_NOT_PENDING"


def test_decide_endpoint_returns_not_found_for_an_unknown_proposal(client):
    goal = _create_goal(client)

    response = client.post(
        f"/api/v1/goals/{goal['id']}/schedule/revision-proposals/999999/decisions",
        json={"decisions": []},
    )

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_decide_endpoint_returns_not_found_when_proposal_belongs_to_another_goal(
    client, monkeypatch
):
    goal_a = _create_goal(client, "目標A")
    goal_b = _create_goal(client, "目標B")
    item = _create_item(client, goal_a["id"], start="2026-12-01", end="2026-12-10")
    FakeAi(monkeypatch, (_change_block(item["id"], "2026-12-05", "2026-12-15"),))
    generated = client.post(
        f"/api/v1/goals/{goal_a['id']}/schedule/revision-proposals",
        json={"trigger": "MANUAL"},
    ).json()
    proposal_id = generated["proposal"]["id"]

    response = client.post(
        f"/api/v1/goals/{goal_b['id']}/schedule/revision-proposals/{proposal_id}/decisions",
        json={"decisions": []},
    )

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "NOT_FOUND"
