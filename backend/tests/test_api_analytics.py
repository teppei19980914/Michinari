"""分析APIのテスト（仕様書6.8 SC-09、データ構造編8章、実装フェーズ分割計画書Phase9）。"""

import datetime as dt

from app.constants.enums import ChatRole, DayType, RecordState
from app.models.record import ChatMessage, DailyRecord, StudyLog
from app.models.setting import CalendarDayOverride
from tests import api_allocation_helpers

TODAY = dt.date.today()


def _override_day_types(session, date_from: dt.date, date_to: dt.date) -> None:
    d = date_from
    while d <= date_to:
        session.add(CalendarDayOverride(target_date=d, day_type=DayType.PLAN))
        d += dt.timedelta(days=1)


def _create_goal_with_subject(client, exam_date_from, exam_date_to, passing_score=None):
    goal = client.post(
        "/api/v1/goals",
        json={"name": "目標A", "start_date": (TODAY - dt.timedelta(days=60)).isoformat()},
    ).json()
    client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "RANGE",
            "exam_date_from": exam_date_from.isoformat(),
            "exam_date_to": exam_date_to.isoformat(),
            "passing_score": passing_score,
        },
    )
    subject_id = client.get(f"/api/v1/goals/{goal['id']}").json()["exam_subjects"][0]["id"]
    return goal, subject_id


def _create_material(client, goal_id, subject_ids, **overrides):
    payload = {
        "name": "教材A",
        "unit_label": "ページ",
        "total_amount": 100,
        "planned_cycles": 2,
        "subject_ids": subject_ids,
        "start_date": (TODAY - dt.timedelta(days=60)).isoformat(),
        "due_date_is_manual": True,
        "due_date": (TODAY + dt.timedelta(days=120)).isoformat(),
    }
    payload.update(overrides)
    response = client.post(f"/api/v1/goals/{goal_id}/materials", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _make_active_goal_with_material(client, passing_score=None, **material_overrides):
    exam_date = TODAY + dt.timedelta(days=180)
    goal, subject_id = _create_goal_with_subject(client, exam_date, exam_date, passing_score)
    material = _create_material(client, goal["id"], [subject_id], **material_overrides)
    api_allocation_helpers.allocate(client, goal["id"])
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text
    return goal, material


def _add_study_log(
    session, record_date: dt.date, material_id: int, cycle_number: int = 1, quality_value=None
) -> None:
    record = session.query(DailyRecord).filter(DailyRecord.record_date == record_date).first()
    if record is None:
        record = DailyRecord(record_date=record_date, exam_record_state=RecordState.PROGRESS_ONLY)
        session.add(record)
        session.flush()
    session.add(
        StudyLog(
            daily_record_id=record.id,
            material_id=material_id,
            minutes_spent=60,
            amount_completed=10,
            cycle_number=cycle_number,
            quality_value=quality_value,
        )
    )
    session.flush()


def test_quality_analytics_returns_series_per_material_with_passing_score(client, seeded_session):
    goal, material = _make_active_goal_with_material(client, passing_score=80.0)
    _add_study_log(seeded_session, TODAY, material["id"], quality_value=60.0)
    seeded_session.commit()

    response = client.get(f"/api/v1/analytics/quality?goal_id={goal['id']}&granularity=DAY")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["granularity"] == "DAY"
    assert len(body["materials"]) == 1
    entry = body["materials"][0]
    assert entry["material_id"] == material["id"]
    assert entry["passing_score"] == 80.0
    assert entry["series"][0]["cycle_number"] == 1
    assert entry["series"][0]["points"][0]["value"] == 60.0


def test_quality_analytics_uses_default_granularity_setting_when_omitted(client, seeded_session):
    goal, material = _make_active_goal_with_material(client)
    _add_study_log(seeded_session, TODAY, material["id"], quality_value=50.0)
    seeded_session.commit()

    response = client.get(f"/api/v1/analytics/quality?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    # 初期値（display.default_granularity）はWEEK（仕様書6.11）
    assert response.json()["granularity"] == "WEEK"


def test_quality_analytics_returns_empty_list_when_goal_has_no_active_materials(
    client, seeded_session
):
    goal = client.post(
        "/api/v1/goals",
        json={"name": "教材なし目標", "start_date": TODAY.isoformat()},
    ).json()

    response = client.get(f"/api/v1/analytics/quality?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    assert response.json()["materials"] == []


def test_quality_analytics_404_when_goal_not_found(client):
    response = client.get("/api/v1/analytics/quality?goal_id=999999")

    assert response.status_code == 404


def test_progress_analytics_includes_actual_and_plan_points(client, seeded_session):
    goal, material = _make_active_goal_with_material(client)
    _override_day_types(seeded_session, TODAY - dt.timedelta(days=60), TODAY + dt.timedelta(days=1))
    _add_study_log(seeded_session, TODAY, material["id"])
    seeded_session.commit()

    response = client.get(f"/api/v1/analytics/progress?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    entry = response.json()["materials"][0]
    assert entry["total_work"] == 200  # total_amount(100) x planned_cycles(2)
    assert entry["actual_points"][-1]["cumulative_completed"] == 10
    # 教材作成時に計画基準値が自動記録されるため（material_service.create_material）、
    # 計画線は空にならない。
    assert len(entry["plan_points"]) > 0


def test_forecast_analytics_returns_entry_per_material(client, seeded_session):
    goal, material = _make_active_goal_with_material(client)

    response = client.get(f"/api/v1/analytics/forecast?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    entry = response.json()["materials"][0]
    assert entry["material_id"] == material["id"]
    # 実績が無いため速度データなし -> 完了予測は算出不能
    assert entry["forecast_date"] is None
    assert entry["unavailable_reason"] == "NO_SPEED_DATA"


def test_speed_analytics_groups_points_by_cycle(client, seeded_session):
    goal, material = _make_active_goal_with_material(client)
    _add_study_log(seeded_session, TODAY, material["id"], cycle_number=1)
    seeded_session.commit()

    response = client.get(f"/api/v1/analytics/speed?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    entry = response.json()["materials"][0]
    assert entry["series"][0]["cycle_number"] == 1
    assert entry["series"][0]["points"][0]["speed"] == 10.0  # 10問/60分 -> 10/h


def test_gantt_analytics_includes_today_and_material_span(client):
    goal, material = _make_active_goal_with_material(client)

    response = client.get(f"/api/v1/analytics/gantt?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["today"] == TODAY.isoformat()
    entry = body["materials"][0]
    assert entry["material_id"] == material["id"]
    assert entry["planned_cycles"] == 2
    assert entry["current_cycle"] == 1


def test_growth_descriptions_returns_assistant_messages_for_goal(client, seeded_session):
    goal = client.post(
        "/api/v1/goals",
        json={"name": "目標A", "start_date": TODAY.isoformat()},
    ).json()
    record = DailyRecord(record_date=TODAY, exam_record_state=RecordState.REPORTED)
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        ChatMessage(
            daily_record_id=record.id,
            goal_id=goal["id"],
            role=ChatRole.ASSISTANT,
            content="成長しています",
            sequence=1,
        )
    )
    seeded_session.commit()

    response = client.get(f"/api/v1/analytics/growth-descriptions?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body[0]["record_date"] == TODAY.isoformat()
    assert body[0]["content"] == "成長しています"
    assert body[0]["goal_id"] == goal["id"]


def test_growth_descriptions_includes_unassigned_legacy_messages(client, seeded_session):
    """移行前のレガシーメッセージ（goal_id=NULL）はpurposeが一致するカテゴリの目標に対して
    「未割り当て」として表示されること（Phase26、未決事項L-07）。"""
    goal = client.post(
        "/api/v1/goals",
        json={"name": "目標A", "start_date": TODAY.isoformat()},
    ).json()
    record = DailyRecord(record_date=TODAY, exam_record_state=RecordState.REPORTED)
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        ChatMessage(
            daily_record_id=record.id, role=ChatRole.ASSISTANT, content="移行前の応答", sequence=1
        )
    )
    seeded_session.commit()

    response = client.get(f"/api/v1/analytics/growth-descriptions?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body[0]["content"] == "移行前の応答"
    assert body[0]["goal_id"] is None


def test_growth_descriptions_empty_when_no_chat_messages(client):
    goal = client.post(
        "/api/v1/goals",
        json={"name": "目標A", "start_date": TODAY.isoformat()},
    ).json()

    response = client.get(f"/api/v1/analytics/growth-descriptions?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_growth_descriptions_404_when_goal_not_found(client):
    response = client.get("/api/v1/analytics/growth-descriptions?goal_id=999999")

    assert response.status_code == 404


def test_assign_growth_description_goal_succeeds(client, seeded_session):
    goal = client.post(
        "/api/v1/goals",
        json={"name": "目標A", "start_date": TODAY.isoformat()},
    ).json()
    record = DailyRecord(record_date=TODAY, exam_record_state=RecordState.REPORTED)
    seeded_session.add(record)
    seeded_session.flush()
    message = ChatMessage(
        daily_record_id=record.id, role=ChatRole.ASSISTANT, content="移行前の応答", sequence=1
    )
    seeded_session.add(message)
    seeded_session.commit()

    response = client.patch(
        f"/api/v1/analytics/growth-descriptions/{message.id}", json={"goal_id": goal["id"]}
    )

    assert response.status_code == 200, response.text
    assert response.json()["goal_id"] == goal["id"]

    follow_up = client.get(f"/api/v1/analytics/growth-descriptions?goal_id={goal['id']}").json()
    assert follow_up[0]["goal_id"] == goal["id"]


def test_assign_growth_description_goal_rejects_category_mismatch(client, seeded_session):
    reading_goal = client.post(
        "/api/v1/goals",
        json={"category": "READING", "name": "読書目標A", "start_date": TODAY.isoformat()},
    ).json()
    record = DailyRecord(record_date=TODAY, exam_record_state=RecordState.REPORTED)
    seeded_session.add(record)
    seeded_session.flush()
    message = ChatMessage(
        daily_record_id=record.id, role=ChatRole.ASSISTANT, content="資格試験の応答", sequence=1
    )
    seeded_session.add(message)
    seeded_session.commit()

    response = client.patch(
        f"/api/v1/analytics/growth-descriptions/{message.id}",
        json={"goal_id": reading_goal["id"]},
    )

    assert response.status_code == 400


def test_assign_growth_description_goal_404_when_message_not_found(client, seeded_session):
    goal = client.post(
        "/api/v1/goals",
        json={"name": "目標A", "start_date": TODAY.isoformat()},
    ).json()

    response = client.patch(
        "/api/v1/analytics/growth-descriptions/999999", json={"goal_id": goal["id"]}
    )

    assert response.status_code == 404


# --- 読書記録タブ（読書目標category=READING向け、Material非依存） ---


def _create_reading_goal_with_book(client, start_date=None):
    start = (start_date or (TODAY - dt.timedelta(days=60))).isoformat()
    goal = client.post(
        "/api/v1/goals",
        json={"category": "READING", "name": "読書目標A", "start_date": start},
    ).json()
    client.post(
        f"/api/v1/goals/{goal['id']}/book",
        json={
            "title": "書籍A",
            "total_pages": 300,
            "start_date": start,
            "due_date": (TODAY + dt.timedelta(days=60)).isoformat(),
        },
    )
    return goal


def test_reading_log_analytics_returns_entries_newest_first(client):
    goal = _create_reading_goal_with_book(client)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    older = (TODAY - dt.timedelta(days=1)).isoformat()
    newer = TODAY.isoformat()
    book_id = client.get(f"/api/v1/goals/{goal['id']}").json()["book"]["id"]
    client.post(
        f"/api/v1/records/{older}/progress",
        json={"reading_logs": [{"book_id": book_id, "recall_body": "1日目の想起"}]},
    )
    client.post(
        f"/api/v1/records/{newer}/progress",
        json={
            "reading_logs": [{"book_id": book_id, "recall_body": "2日目の想起", "pages_read": 10}]
        },
    )

    response = client.get(f"/api/v1/analytics/reading-logs?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert [e["record_date"] for e in body] == [newer, older]
    assert body[0]["recall_body"] == "2日目の想起"
    assert body[0]["pages_read"] == 10


def test_reading_log_analytics_returns_empty_when_book_not_registered(client):
    goal = client.post(
        "/api/v1/goals",
        json={"category": "READING", "name": "書籍未登録", "start_date": TODAY.isoformat()},
    ).json()

    response = client.get(f"/api/v1/analytics/reading-logs?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_reading_log_analytics_404_when_goal_not_found(client):
    response = client.get("/api/v1/analytics/reading-logs?goal_id=999999")

    assert response.status_code == 404


# --- 業務記録タブ（仕事目標category=WORK向け、Material非依存） ---


def _create_work_goal_with_assignment(client, start_date=None):
    start = (start_date or (TODAY - dt.timedelta(days=60))).isoformat()
    goal = client.post(
        "/api/v1/goals",
        json={"category": "WORK", "name": "仕事目標A", "start_date": start},
    ).json()
    client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment",
        json={"expected_content": "想定業務内容", "start_date": start},
    )
    return goal


def test_work_log_analytics_returns_entries_newest_first(client):
    goal = _create_work_goal_with_assignment(client)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    older = (TODAY - dt.timedelta(days=1)).isoformat()
    newer = TODAY.isoformat()
    work_assignment_id = client.get(f"/api/v1/goals/{goal['id']}").json()["work_assignment"]["id"]
    client.post(
        f"/api/v1/records/{older}/progress",
        json={"work_logs": [{"work_assignment_id": work_assignment_id, "body": "1日目の業務"}]},
    )
    client.post(
        f"/api/v1/records/{newer}/progress",
        json={"work_logs": [{"work_assignment_id": work_assignment_id, "body": "2日目の業務"}]},
    )

    response = client.get(f"/api/v1/analytics/work-logs?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert [e["record_date"] for e in body] == [newer, older]
    assert body[0]["body"] == "2日目の業務"


def test_work_log_analytics_returns_empty_when_assignment_not_registered(client):
    goal = client.post(
        "/api/v1/goals",
        json={"category": "WORK", "name": "案件未登録", "start_date": TODAY.isoformat()},
    ).json()

    response = client.get(f"/api/v1/analytics/work-logs?goal_id={goal['id']}")

    assert response.status_code == 200, response.text
    assert response.json() == []


def test_work_log_analytics_404_when_goal_not_found(client):
    response = client.get("/api/v1/analytics/work-logs?goal_id=999999")

    assert response.status_code == 404
