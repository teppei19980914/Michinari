"""教材APIのテスト（データ構造編6.2、仕様書6.2・10章）。"""

import datetime as dt

import pytest

from app.constants.enums import RecordState
from app.models.record import DailyRecord, StudyLog


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
        "due_date_is_manual": False,
    }
    payload.update(overrides)
    response = client.post(f"/api/v1/goals/{goal_id}/materials", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_material_derives_due_date_from_subject(client):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(client, goal["id"], [subject_id])
    assert material["due_date"] == "2026-05-31"
    assert material["total_work"] == 100.0
    assert material["current_cycle"] == 1
    assert material["remaining"] == 100.0


def test_create_material_rejects_start_after_due_date(client):
    goal, subject_id = _create_goal_with_subject(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/materials",
        json={
            "name": "教材A",
            "unit_label": "ページ",
            "total_amount": 100,
            "planned_cycles": 1,
            "subject_ids": [subject_id],
            "start_date": "2026-06-01",
            "due_date_is_manual": False,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_material_subject_link_recalculates_due_date_and_records_baseline(client):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(client, goal["id"], [subject_id])

    client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "科目B",
            "exam_date_type": "RANGE",
            "exam_date_from": "2026-04-01",
            "exam_date_to": "2026-04-10",
        },
    )
    subjects = client.get(f"/api/v1/goals/{goal['id']}").json()["exam_subjects"]
    subject_b_id = next(s["id"] for s in subjects if s["name"] == "科目B")

    updated = client.patch(
        f"/api/v1/materials/{material['id']}", json={"subject_ids": [subject_id, subject_b_id]}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["due_date"] == "2026-03-31"

    baselines = client.get(f"/api/v1/goals/{goal['id']}/baselines").json()
    reasons = [b["reason"] for b in baselines]
    assert "MATERIAL_CHANGED" in reasons


def test_update_material_planned_cycles_below_completed_is_rejected(client, seeded_session):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(
        client, goal["id"], [subject_id], total_amount=100, planned_cycles=3
    )

    record = DailyRecord(record_date=dt.date(2026, 1, 5), exam_record_state=RecordState.REPORTED)
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        StudyLog(
            daily_record_id=record.id,
            material_id=material["id"],
            minutes_spent=100,
            amount_completed=250,
            cycle_number=3,
        )
    )
    seeded_session.flush()

    response = client.patch(f"/api/v1/materials/{material['id']}", json={"planned_cycles": 2})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CYCLE_CONFLICT"


def test_update_material_planned_cycles_change_records_cycle_changed_baseline(client):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(client, goal["id"], [subject_id], planned_cycles=1)

    response = client.patch(f"/api/v1/materials/{material['id']}", json={"planned_cycles": 2})
    assert response.status_code == 200, response.text
    assert response.json()["planned_cycles"] == 2

    baselines = client.get(f"/api/v1/goals/{goal['id']}/baselines").json()
    reasons = [b["reason"] for b in baselines]
    assert "CYCLE_CHANGED" in reasons


def test_delete_material_without_logs_succeeds(client):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(client, goal["id"], [subject_id])

    response = client.delete(f"/api/v1/materials/{material['id']}")
    assert response.status_code == 204


def test_delete_material_with_study_logs_is_rejected(client, seeded_session):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(client, goal["id"], [subject_id])

    record = DailyRecord(record_date=dt.date(2026, 1, 5), exam_record_state=RecordState.REPORTED)
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        StudyLog(
            daily_record_id=record.id,
            material_id=material["id"],
            minutes_spent=30,
            amount_completed=10,
            cycle_number=1,
        )
    )
    seeded_session.flush()

    response = client.delete(f"/api/v1/materials/{material['id']}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_deactivate_material(client):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(client, goal["id"], [subject_id])

    response = client.post(f"/api/v1/materials/{material['id']}/deactivate")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_slot_check_endpoint(client):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(client, goal["id"], [subject_id])

    response = client.get(f"/api/v1/materials/{material['id']}/slot-check")
    assert response.status_code == 200
    assert response.json() == {"sufficient": False}


def test_cycle_progress_endpoint(client, seeded_session):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(
        client, goal["id"], [subject_id], total_amount=100, planned_cycles=2
    )

    record = DailyRecord(record_date=dt.date(2026, 1, 5), exam_record_state=RecordState.REPORTED)
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        StudyLog(
            daily_record_id=record.id,
            material_id=material["id"],
            minutes_spent=60,
            amount_completed=50,
            cycle_number=1,
            quality_value=80.0,
        )
    )
    seeded_session.flush()

    # 2周目の実績も追加し、複数周回のspeedが一括取得（compute_cycle_speeds）でも
    # 混同されず正しく分離されることをAPI経由で確認する。
    record2 = DailyRecord(record_date=dt.date(2026, 1, 6), exam_record_state=RecordState.REPORTED)
    seeded_session.add(record2)
    seeded_session.flush()
    seeded_session.add(
        StudyLog(
            daily_record_id=record2.id,
            material_id=material["id"],
            minutes_spent=30,
            amount_completed=20,
            cycle_number=2,
            quality_value=60.0,
        )
    )
    seeded_session.flush()

    response = client.get(f"/api/v1/materials/{material['id']}/cycles")
    assert response.status_code == 200
    body = response.json()
    cycle_one = next(c for c in body if c["cycle_number"] == 1)
    assert cycle_one["completed_amount"] == 50.0
    assert cycle_one["speed"] == pytest.approx(50.0)

    cycle_two = next(c for c in body if c["cycle_number"] == 2)
    assert cycle_two["completed_amount"] == 20.0
    assert cycle_two["speed"] == pytest.approx(40.0)
    assert cycle_two["quality_average"] == 60.0
    assert cycle_one["quality_average"] == 80.0


def test_create_material_rejects_nonexistent_subject(client):
    goal, _subject_id = _create_goal_with_subject(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/materials",
        json={
            "name": "教材A",
            "unit_label": "ページ",
            "total_amount": 100,
            "planned_cycles": 1,
            "subject_ids": [9999],
            "start_date": "2026-01-01",
            "due_date_is_manual": False,
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_create_material_rejects_subject_from_other_goal(client):
    goal, subject_id = _create_goal_with_subject(client)
    other_goal, other_subject_id = _create_goal_with_subject(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/materials",
        json={
            "name": "教材A",
            "unit_label": "ページ",
            "total_amount": 100,
            "planned_cycles": 1,
            "subject_ids": [subject_id, other_subject_id],
            "start_date": "2026-01-01",
            "due_date_is_manual": False,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_material_manual_due_date_requires_due_date(client):
    goal, subject_id = _create_goal_with_subject(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/materials",
        json={
            "name": "教材A",
            "unit_label": "ページ",
            "total_amount": 100,
            "planned_cycles": 1,
            "subject_ids": [subject_id],
            "start_date": "2026-01-01",
            "due_date_is_manual": True,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_material_with_manual_due_date(client):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(
        client, goal["id"], [subject_id], due_date_is_manual=True, due_date="2026-12-31"
    )
    assert material["due_date"] == "2026-12-31"
    assert material["due_date_is_manual"] is True


def test_update_material_switches_to_manual_due_date(client):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(client, goal["id"], [subject_id])

    response = client.patch(
        f"/api/v1/materials/{material['id']}",
        json={"due_date_is_manual": True, "due_date": "2026-12-31"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["due_date"] == "2026-12-31"
    assert response.json()["due_date_is_manual"] is True

    # 手動締切のまま締切日を指定しない更新では、既存の締切が保持される。
    unchanged = client.patch(f"/api/v1/materials/{material['id']}", json={"name": "改名のみ"})
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["due_date"] == "2026-12-31"


def test_update_material_rejects_start_after_due_date(client):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(client, goal["id"], [subject_id])

    response = client.patch(
        f"/api/v1/materials/{material['id']}", json={"start_date": "2026-12-31"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_material_simple_fields(client):
    goal, subject_id = _create_goal_with_subject(client)
    material = _create_material(client, goal["id"], [subject_id])

    response = client.patch(
        f"/api/v1/materials/{material['id']}",
        json={
            "name": "改名教材",
            "unit_label": "問",
            "total_amount": 150,
            "required_block_minutes": 30,
            "required_environment": "PC",
            "quality_metric_type": "OBJECTIVE",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "改名教材"
    assert body["unit_label"] == "問"
    assert body["total_amount"] == 150
    assert body["required_block_minutes"] == 30
    assert body["required_environment"] == "PC"
    assert body["quality_metric_type"] == "OBJECTIVE"


def test_update_missing_material_returns_404(client):
    response = client.patch("/api/v1/materials/9999", json={"name": "x"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
