"""日次記録APIのテスト（データ構造編6.2、仕様書6.4〜6.7・7.2章、実装フェーズ分割計画書Phase4）。

logical_date（1日の境界時刻を考慮した論理的な本日）は calendar.day_boundary_hour=0（初期値）
のため常にシステム日付と一致する。この前提のもと dt.date.today() を基準に相対日付でテストする。
"""

import datetime as dt


def _create_goal_with_subject(client, exam_date_from="2026-06-01", exam_date_to="2026-06-10"):
    goal = client.post("/api/v1/goals", json={"name": "目標A", "start_date": "2026-01-01"}).json()
    client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "RANGE",
            "exam_date_from": exam_date_from,
            "exam_date_to": exam_date_to,
        },
    )
    subject_id = client.get(f"/api/v1/goals/{goal['id']}").json()["exam_subjects"][0]["id"]
    return goal, subject_id


def _create_material(client, goal_id, subject_ids, **overrides):
    payload = {
        "name": "教材A",
        "unit_label": "ページ",
        "total_amount": 100,
        "planned_cycles": 1,
        "subject_ids": subject_ids,
        "start_date": "2026-01-01",
        "due_date_is_manual": True,
        "due_date": "2027-12-31",
    }
    payload.update(overrides)
    response = client.post(f"/api/v1/goals/{goal_id}/materials", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _make_active_goal_with_material(client, **material_overrides):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(client, goal["id"], [subject_id], **material_overrides)
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text
    return goal, material


# --- GET /records/today, GET /records/{date} ---


def test_get_today_returns_logical_date_and_null_state_when_not_entered(client):
    response = client.get("/api/v1/records/today")
    assert response.status_code == 200
    body = response.json()
    assert body["logical_date"] == dt.date.today().isoformat()
    assert body["record_state"] is None


def test_get_record_for_unentered_date_returns_empty_structure(client):
    target = dt.date.today().isoformat()
    response = client.get(f"/api/v1/records/{target}")
    assert response.status_code == 200
    body = response.json()
    assert body["record_state"] is None
    assert body["study_logs"] == []
    assert body["comments"] == []
    assert body["diary_body"] is None


# --- POST /records/{date}/progress ---


def test_register_progress_endpoint_creates_progress_only_record(client):
    _goal, material = _make_active_goal_with_material(client)
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={
            "study_logs": [
                {"material_id": material["id"], "minutes_spent": 30, "amount_completed": 10}
            ]
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record_state"] == "PROGRESS_ONLY"
    assert len(body["study_logs"]) == 1
    assert body["study_logs"][0]["cycle_number"] == 1


def test_register_progress_endpoint_rejects_future_date(client):
    _goal, material = _make_active_goal_with_material(client)
    future = (dt.date.today() + dt.timedelta(days=1)).isoformat()

    response = client.post(
        f"/api/v1/records/{future}/progress",
        json={
            "study_logs": [
                {"material_id": material["id"], "minutes_spent": 30, "amount_completed": 10}
            ]
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_register_progress_endpoint_rejects_unknown_material(client):
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={"study_logs": [{"material_id": 9999, "minutes_spent": 30, "amount_completed": 10}]},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- POST /records/{date}/finalize ---


def test_finalize_endpoint_marks_reported_and_reflects_in_today(client):
    _goal, material = _make_active_goal_with_material(client)
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/finalize",
        json={
            "study_logs": [
                {"material_id": material["id"], "minutes_spent": 30, "amount_completed": 10}
            ],
            "diary_body": "今日はよく頑張った",
            "diary_learned": "過去問を解いた",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["record_state"] == "REPORTED"
    assert body["diary_body"] == "今日はよく頑張った"

    today_response = client.get("/api/v1/records/today")
    assert today_response.json()["record_state"] == "REPORTED"


def test_finalize_endpoint_rejects_backdate_beyond_yesterday(client):
    two_days_ago = (dt.date.today() - dt.timedelta(days=2)).isoformat()

    response = client.post(
        f"/api/v1/records/{two_days_ago}/finalize",
        json={"study_logs": [], "diary_body": "所感", "diary_learned": "学び"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BACKDATE_LIMIT_EXCEEDED"


def test_finalize_endpoint_rejects_update_after_reported(client):
    target = dt.date.today().isoformat()
    client.post(
        f"/api/v1/records/{target}/finalize",
        json={"study_logs": [], "diary_body": "所感", "diary_learned": "学び"},
    )

    response = client.post(
        f"/api/v1/records/{target}/finalize",
        json={"study_logs": [], "diary_body": "上書き", "diary_learned": "上書き"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IMMUTABLE_RECORD"


def test_progress_endpoint_rejects_update_after_reported(client):
    _goal, material = _make_active_goal_with_material(client)
    target = dt.date.today().isoformat()
    client.post(
        f"/api/v1/records/{target}/finalize",
        json={"study_logs": [], "diary_body": "所感", "diary_learned": "学び"},
    )

    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={
            "study_logs": [
                {"material_id": material["id"], "minutes_spent": 30, "amount_completed": 10}
            ]
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IMMUTABLE_RECORD"


# --- GET /records/{date}/quota ---


def test_quota_endpoint_returns_items_for_active_goal_material(client):
    _goal, material = _make_active_goal_with_material(client, total_amount=100, planned_cycles=1)
    target = dt.date.today().isoformat()

    response = client.get(f"/api/v1/records/{target}/quota")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["material_id"] == material["id"]
    assert body[0]["current_cycle"] == 1


# --- コメント ---


def test_comment_create_update_delete_flow(client):
    target = dt.date.today().isoformat()
    client.post(
        f"/api/v1/records/{target}/finalize",
        json={"study_logs": [], "diary_body": "所感", "diary_learned": "学び"},
    )

    created = client.post(f"/api/v1/records/{target}/comments", json={"body": "初回コメント"})
    assert created.status_code == 201, created.text
    comment_id = created.json()["id"]

    updated = client.patch(f"/api/v1/comments/{comment_id}", json={"body": "修正後コメント"})
    assert updated.status_code == 200
    assert updated.json()["body"] == "修正後コメント"

    record = client.get(f"/api/v1/records/{target}").json()
    assert record["comments"][0]["body"] == "修正後コメント"

    deleted = client.delete(f"/api/v1/comments/{comment_id}")
    assert deleted.status_code == 204

    record_after_delete = client.get(f"/api/v1/records/{target}").json()
    assert record_after_delete["comments"] == []


def test_comment_create_for_unentered_date_returns_404(client):
    target = dt.date.today().isoformat()
    response = client.post(f"/api/v1/records/{target}/comments", json={"body": "コメント"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_update_missing_comment_returns_404(client):
    response = client.patch("/api/v1/comments/9999", json={"body": "x"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
