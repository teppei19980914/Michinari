"""分析APIのテスト（仕様書6.8 SC-09、データ構造編8章、実装フェーズ分割計画書Phase9）。"""

import datetime as dt

from app.constants.enums import ChatRole, DayType, RecordState
from app.models.record import ChatMessage, DailyRecord, StudyLog
from app.models.setting import CalendarDayOverride

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
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text
    return goal, material


def _add_study_log(
    session, record_date: dt.date, material_id: int, cycle_number: int = 1, quality_value=None
) -> None:
    record = session.query(DailyRecord).filter(DailyRecord.record_date == record_date).first()
    if record is None:
        record = DailyRecord(record_date=record_date, record_state=RecordState.PROGRESS_ONLY)
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


def test_growth_descriptions_returns_assistant_messages_across_goals(client, seeded_session):
    record = DailyRecord(record_date=TODAY, record_state=RecordState.REPORTED)
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        ChatMessage(
            daily_record_id=record.id, role=ChatRole.ASSISTANT, content="成長しています", sequence=1
        )
    )
    seeded_session.commit()

    response = client.get("/api/v1/analytics/growth-descriptions")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body[0]["record_date"] == TODAY.isoformat()
    assert body[0]["content"] == "成長しています"


def test_growth_descriptions_empty_when_no_chat_messages(client):
    response = client.get("/api/v1/analytics/growth-descriptions")

    assert response.status_code == 200, response.text
    assert response.json() == []
