"""スケジュール・ガントチャート機能のAPIテスト（開発Todo_スケジュール・ガントチャート_v1.1
第8章、単位2）。

検証ルールの分岐・差分更新自体はtest_schedule_service.pyで検証済みのため、ここではAPI層
の配線（ステータスコード・エラーコード）、認可境界、SQLインジェクション・XSSペイロードの
保存・取得、終了した目標への書き込み拒否を中心に確認する。
"""

from app.constants.enums import GoalStatus
from tests import schedule_helpers


def _create_goal(client, name: str = "目標A") -> dict:
    return client.post("/api/v1/goals", json={"name": name, "start_date": "2026-01-01"}).json()


def test_get_schedule_returns_defaults_for_new_goal(client):
    goal = _create_goal(client)
    response = client.get(f"/api/v1/goals/{goal['id']}/schedule")
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 0
    assert body["frozen_row_count"] == 0
    assert body["frozen_column_count"] == 1
    assert body["columns"] == []
    assert body["items"] == []
    assert body["today"] == "2026-11-23"


def test_get_schedule_returns_404_for_nonexistent_goal(client):
    response = client.get("/api/v1/goals/9999/schedule")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_put_schedule_creates_item_and_column_and_returns_assigned_ids(client):
    goal = _create_goal(client)
    response = client.put(
        f"/api/v1/goals/{goal['id']}/schedule",
        json={
            "revision": 0,
            "columns": [{"temp_key": "c1", "name": "担当"}],
            "items": [
                {
                    "title": "第1章",
                    "planned_start_date": "2026-01-01",
                    "planned_end_date": "2026-01-05",
                    "status": "NOT_STARTED",
                    "cells": [{"column_temp_key": "c1", "value": "自分"}],
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 1
    assert isinstance(body["items"][0]["id"], int)
    assert isinstance(body["columns"][0]["id"], int)
    assert body["items"][0]["cells"] == [{"column_id": body["columns"][0]["id"], "value": "自分"}]


def test_put_schedule_rejects_stale_revision(client):
    goal = _create_goal(client)
    client.put(
        f"/api/v1/goals/{goal['id']}/schedule",
        json={
            "revision": 0,
            "items": [
                {
                    "title": "第1章",
                    "planned_start_date": "2026-01-01",
                    "planned_end_date": "2026-01-05",
                    "status": "NOT_STARTED",
                }
            ],
        },
    )
    response = client.put(f"/api/v1/goals/{goal['id']}/schedule", json={"revision": 0, "items": []})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SCHEDULE_REVISION_CONFLICT"


def test_put_schedule_rejects_item_id_belonging_to_another_goal(client):
    goal_a = _create_goal(client, "目標A")
    goal_b = _create_goal(client, "目標B")
    created = client.put(
        f"/api/v1/goals/{goal_b['id']}/schedule",
        json={
            "revision": 0,
            "items": [
                {
                    "title": "目標Bの行",
                    "planned_start_date": "2026-01-01",
                    "planned_end_date": "2026-01-05",
                    "status": "NOT_STARTED",
                }
            ],
        },
    ).json()
    other_item_id = created["items"][0]["id"]

    response = client.put(
        f"/api/v1/goals/{goal_a['id']}/schedule",
        json={
            "revision": 0,
            "items": [
                {
                    "id": other_item_id,
                    "title": "乗っ取り",
                    "planned_start_date": "2026-01-01",
                    "planned_end_date": "2026-01-05",
                    "status": "NOT_STARTED",
                }
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    # 目標Aには何も反映されず、目標Bの行もそのまま残っていること。
    goal_a_schedule = client.get(f"/api/v1/goals/{goal_a['id']}/schedule").json()
    assert goal_a_schedule["items"] == []
    goal_b_schedule = client.get(f"/api/v1/goals/{goal_b['id']}/schedule").json()
    assert goal_b_schedule["items"][0]["title"] == "目標Bの行"


def test_put_schedule_rejects_column_id_belonging_to_another_goal(client):
    goal_a = _create_goal(client, "目標A")
    goal_b = _create_goal(client, "目標B")
    created = client.put(
        f"/api/v1/goals/{goal_b['id']}/schedule",
        json={"revision": 0, "columns": [{"temp_key": "c1", "name": "目標Bの列"}]},
    ).json()
    other_column_id = created["columns"][0]["id"]

    response = client.put(
        f"/api/v1/goals/{goal_a['id']}/schedule",
        json={"revision": 0, "columns": [{"id": other_column_id, "name": "乗っ取り"}]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    # どちらの目標の列も変化しないこと（認可境界レビュー指摘）。
    goal_a_schedule = client.get(f"/api/v1/goals/{goal_a['id']}/schedule").json()
    assert goal_a_schedule["columns"] == []
    goal_b_schedule = client.get(f"/api/v1/goals/{goal_b['id']}/schedule").json()
    assert goal_b_schedule["columns"][0]["name"] == "目標Bの列"


def test_put_schedule_stores_and_returns_sql_and_xss_payloads_verbatim(client):
    """SQLインジェクション・XSSのペイロードを含む文字が、そのまま保存・取得されること
    （パラメータ化クエリ前提。保存層でのサニタイズ・無害化は行わない設計。入力を
    そのまま埋め込んで実行する文字列結合は使わない。描画時のエスケープはフロント側の
    責務であり、本単位〈バックエンド〉のAPIはそのまま往復することだけを保証する）。
    """
    goal = _create_goal(client)
    sql_payload = "'; DROP TABLE goal; --"
    xss_payload = "<" + "script>alert('xss')</" + "script>"
    response = client.put(
        f"/api/v1/goals/{goal['id']}/schedule",
        json={
            "revision": 0,
            "columns": [{"temp_key": "c1", "name": xss_payload}],
            "items": [
                {
                    "title": sql_payload,
                    "description": xss_payload,
                    "planned_start_date": "2026-01-01",
                    "planned_end_date": "2026-01-05",
                    "status": "NOT_STARTED",
                    "cells": [{"column_temp_key": "c1", "value": sql_payload + xss_payload}],
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"][0]["title"] == sql_payload
    assert body["items"][0]["description"] == xss_payload
    assert body["columns"][0]["name"] == xss_payload
    assert body["items"][0]["cells"][0]["value"] == sql_payload + xss_payload

    # 他のテーブル・他の行に影響していないこと（SQLiが実際には起きていないことの確認）。
    goals_after = client.get("/api/v1/goals").json()
    assert any(g["id"] == goal["id"] for g in goals_after)

    refetched = client.get(f"/api/v1/goals/{goal['id']}/schedule").json()
    assert refetched["items"][0]["title"] == sql_payload
    assert refetched["columns"][0]["name"] == xss_payload


def test_put_schedule_rejects_closed_goal(seeded_session, client):
    goal = schedule_helpers.make_goal(seeded_session, status=GoalStatus.CLOSED_WITH_RESULT)
    response = client.put(f"/api/v1/goals/{goal.id}/schedule", json={"revision": 0, "items": []})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_put_view_setting_updates_without_changing_revision(client):
    goal = _create_goal(client)
    saved = client.put(
        f"/api/v1/goals/{goal['id']}/schedule",
        json={
            "revision": 0,
            "items": [
                {
                    "title": "第1章",
                    "planned_start_date": "2026-01-01",
                    "planned_end_date": "2026-01-05",
                    "status": "NOT_STARTED",
                }
            ],
        },
    ).json()
    assert saved["revision"] == 1

    response = client.put(
        f"/api/v1/goals/{goal['id']}/schedule/view-setting",
        json={"frozen_row_count": 1, "frozen_column_count": 3},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"frozen_row_count": 1, "frozen_column_count": 3}

    after = client.get(f"/api/v1/goals/{goal['id']}/schedule").json()
    assert after["revision"] == 1  # view-settingではrevisionを変えない（D-24）


def test_put_view_setting_rejects_closed_goal(seeded_session, client):
    goal = schedule_helpers.make_goal(seeded_session, status=GoalStatus.CLOSED_WITH_RESULT)
    response = client.put(
        f"/api/v1/goals/{goal.id}/schedule/view-setting",
        json={"frozen_row_count": 0, "frozen_column_count": 1},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
