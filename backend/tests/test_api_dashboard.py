"""ダッシュボードAPIのテスト（仕様書6.1 SC-01、実装フェーズ分割計画書Phase6）。

logical_date は calendar.day_boundary_hour=0（初期値）のため常にシステム日付と一致する
（test_api_records.pyと同じ前提）。日種別は実行日の曜日に依存させないよう、必要な範囲を
CalendarDayOverrideでPLANに固定してから検証する。
"""

import datetime as dt

from app.api.dashboard import _goal_remaining_days
from app.constants.enums import DayType, GoalStatus, RecordState
from app.models.goal import Goal
from app.models.record import DailyRecord, StudyLog
from app.models.setting import AppSetting, CalendarDayOverride

TODAY = dt.date.today()


def _override_day_types(session, date_from: dt.date, date_to: dt.date) -> None:
    d = date_from
    while d <= date_to:
        session.add(CalendarDayOverride(target_date=d, day_type=DayType.PLAN))
        d += dt.timedelta(days=1)


def _create_goal_with_subject(client, exam_date_from, exam_date_to, name="目標A"):
    goal = client.post(
        "/api/v1/goals",
        json={"name": name, "start_date": (TODAY - dt.timedelta(days=60)).isoformat()},
    ).json()
    client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "RANGE",
            "exam_date_from": exam_date_from.isoformat(),
            "exam_date_to": exam_date_to.isoformat(),
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
        "start_date": (TODAY - dt.timedelta(days=60)).isoformat(),
        "due_date_is_manual": True,
        "due_date": (TODAY + dt.timedelta(days=120)).isoformat(),
    }
    payload.update(overrides)
    response = client.post(f"/api/v1/goals/{goal_id}/materials", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _make_active_goal_with_material(
    client, exam_offset_days=180, goal_name="目標A", **material_overrides
):
    exam_date = TODAY + dt.timedelta(days=exam_offset_days)
    goal, subject_id = _create_goal_with_subject(client, exam_date, exam_date, name=goal_name)
    material = _create_material(client, goal["id"], [subject_id], **material_overrides)
    client.patch(f"/api/v1/goals/{goal['id']}", json={"resource_ratio": 0.1})
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text
    return goal, material


def _add_study_log(session, record_date: dt.date, material_id: int, cycle_number: int = 1) -> None:
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
        )
    )
    session.flush()


def test_dashboard_returns_empty_lists_when_no_active_goals(client, seeded_session):
    _override_day_types(seeded_session, TODAY, TODAY)
    seeded_session.commit()

    response = client.get("/api/v1/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "logical_date": TODAY.isoformat(),
        "record_state": None,
        "today_day_type": "PLAN",
        "report_rate_window_days": 30,
        "goal_cards": [],
        "goal_stats": [],
        "today_quota": [],
        "available_slot_names": [],
    }


def test_dashboard_includes_logical_date_and_record_state_without_a_separate_call(
    client, seeded_session
):
    """データ構造編6.2「複数のリソースを個別に取得せず1回の呼び出しで返す」。
    GET /records/today を別途呼ばなくても、ダッシュボード画面に必要な本日の状態が
    /dashboard 単独で取得できることを確認する。
    """
    _goal, material = _make_active_goal_with_material(client)
    target = TODAY.isoformat()
    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={
            "study_logs": [
                {"material_id": material["id"], "minutes_spent": 30, "amount_completed": 10}
            ]
        },
    )
    assert response.status_code == 200, response.text

    body = client.get("/api/v1/dashboard").json()

    assert body["logical_date"] == target
    assert body["record_state"] == "PROGRESS_ONLY"


def test_dashboard_reports_buffer_day_type(client, seeded_session):
    seeded_session.add(CalendarDayOverride(target_date=TODAY, day_type=DayType.BUFFER))
    seeded_session.commit()

    body = client.get("/api/v1/dashboard").json()

    assert body["today_day_type"] == "BUFFER"


def test_dashboard_goal_card_progress_rate_and_remaining_days(client, seeded_session):
    _override_day_types(seeded_session, TODAY - dt.timedelta(days=1), TODAY)
    seeded_session.commit()
    goal, material = _make_active_goal_with_material(client, exam_offset_days=200)
    _add_study_log(seeded_session, TODAY - dt.timedelta(days=1), material["id"])
    seeded_session.commit()

    body = client.get("/api/v1/dashboard").json()

    assert len(body["goal_cards"]) == 1
    card = body["goal_cards"][0]
    assert card["goal_id"] == goal["id"]
    assert card["progress_rate"] == 10 / 100  # 単一教材のため教材自身の進捗率と一致
    assert card["remaining_days"] == 200
    assert card["has_warning"] is False


def test_dashboard_goal_card_has_warning_true_when_quota_ratio_exceeds_threshold(
    client, seeded_session
):
    _override_day_types(seeded_session, TODAY, TODAY)
    seeded_session.commit()
    goal, _material = _make_active_goal_with_material(client)
    # 活動時点のbaselineに対し、閾値を極端に下げることでノルマ比率の超過を発生させる。
    seeded_session.query(AppSetting).filter_by(key="threshold.warning_ratio").update(
        {"value": "0.01"}
    )
    seeded_session.commit()

    body = client.get("/api/v1/dashboard").json()

    assert body["goal_cards"][0]["has_warning"] is True


def test_dashboard_goal_card_no_warning_for_material_before_start_date(client, seeded_session):
    """学習期間開始前の教材は、閾値を極端に下げても警告バッジの対象にならないこと。

    quota_service.compute_material_quotaが今日のノルマを0として扱うため、活動時点の
    baseline自体が0で記録され、check_warningのbaseline<=0ガードで常にFalseとなる。
    """
    _override_day_types(seeded_session, TODAY, TODAY)
    seeded_session.commit()
    goal, _material = _make_active_goal_with_material(
        client, start_date=(TODAY + dt.timedelta(days=1)).isoformat()
    )
    seeded_session.query(AppSetting).filter_by(key="threshold.warning_ratio").update(
        {"value": "0.01"}
    )
    seeded_session.commit()

    body = client.get("/api/v1/dashboard").json()

    assert body["goal_cards"][0]["has_warning"] is False


def test_dashboard_goal_card_empty_when_all_materials_inactive(client, seeded_session):
    goal, material = _make_active_goal_with_material(client)
    client.post(f"/api/v1/materials/{material['id']}/deactivate")

    body = client.get("/api/v1/dashboard").json()

    card = body["goal_cards"][0]
    assert card["progress_rate"] is None
    assert card["forecast_deviation_days"] is None
    assert card["has_warning"] is False
    assert card["has_forced_replan"] is False
    assert body["goal_stats"][0]["material_speeds"] == []


def test_dashboard_material_speed_and_target_minutes_available_after_three_samples(
    client, seeded_session
):
    _override_day_types(seeded_session, TODAY - dt.timedelta(days=3), TODAY)
    seeded_session.commit()
    _goal, material = _make_active_goal_with_material(client)
    for offset in (3, 2, 1):
        _add_study_log(seeded_session, TODAY - dt.timedelta(days=offset), material["id"])
    seeded_session.commit()

    body = client.get("/api/v1/dashboard").json()

    speeds = body["goal_stats"][0]["material_speeds"]
    assert len(speeds) == 1
    assert speeds[0]["speed"] == 10.0  # 30サンプル分（10分量/1時間）× 3件

    quota_entries = [e for e in body["today_quota"] if e["material_id"] == material["id"]]
    assert len(quota_entries) == 1
    assert quota_entries[0]["target_minutes"] is not None


def test_dashboard_today_quota_target_minutes_none_when_speed_unavailable(client, seeded_session):
    _override_day_types(seeded_session, TODAY, TODAY)
    seeded_session.commit()
    _goal, material = _make_active_goal_with_material(client)

    body = client.get("/api/v1/dashboard").json()

    quota_entries = [e for e in body["today_quota"] if e["material_id"] == material["id"]]
    assert len(quota_entries) == 1
    assert quota_entries[0]["target_minutes"] is None
    assert quota_entries[0]["current_cycle"] == 1


def test_dashboard_today_quota_excludes_material_before_start_date(client, seeded_session):
    _override_day_types(seeded_session, TODAY, TODAY)
    seeded_session.commit()
    _goal, material = _make_active_goal_with_material(
        client, start_date=(TODAY + dt.timedelta(days=1)).isoformat()
    )

    body = client.get("/api/v1/dashboard").json()

    quota_entries = [e for e in body["today_quota"] if e["material_id"] == material["id"]]
    assert quota_entries == []


def test_dashboard_available_slot_names_filtered_by_weekday(client):
    other_weekday = (TODAY.weekday() + 1) % 7
    client.post(
        "/api/v1/resources/slots",
        json={
            "name": "本日のスロット",
            "start_time": "19:00:00",
            "end_time": "21:00:00",
            "environment": "PC",
            "weekdays": [TODAY.weekday()],
        },
    )
    client.post(
        "/api/v1/resources/slots",
        json={
            "name": "別曜日のスロット",
            "start_time": "19:00:00",
            "end_time": "21:00:00",
            "environment": "PC",
            "weekdays": [other_weekday],
        },
    )

    body = client.get("/api/v1/dashboard").json()

    assert body["available_slot_names"] == ["本日のスロット"]


def test_dashboard_multiple_active_goals_each_produce_own_card_and_stats(client):
    goal_a, material_a = _make_active_goal_with_material(
        client, exam_offset_days=100, goal_name="目標A"
    )
    goal_b, material_b = _make_active_goal_with_material(
        client, exam_offset_days=50, goal_name="目標B"
    )

    body = client.get("/api/v1/dashboard").json()

    goal_ids = {card["goal_id"] for card in body["goal_cards"]}
    assert goal_ids == {goal_a["id"], goal_b["id"]}
    assert len(body["goal_stats"]) == 2

    # 「本日のノルマ」一覧も、教材ごとに正しい目標へ帰属していること（L-04関連）。
    quota_by_material = {item["material_id"]: item for item in body["today_quota"]}
    assert quota_by_material[material_a["id"]]["goal_id"] == goal_a["id"]
    assert quota_by_material[material_a["id"]]["goal_name"] == "目標A"
    assert quota_by_material[material_b["id"]]["goal_id"] == goal_b["id"]
    assert quota_by_material[material_b["id"]]["goal_name"] == "目標B"


def test_dashboard_reading_goal_card_shows_book_progress(client, seeded_session):
    """読書目標のカードは日次ノルマ等ではなく書籍の派生値（残日数・ページ進捗）で表示する
    （要件定義書R-71、実装フェーズ分割計画書Phase17）。"""
    goal = client.post(
        "/api/v1/goals",
        json={"category": "READING", "name": "読書目標A", "start_date": TODAY.isoformat()},
    ).json()
    book = client.post(
        f"/api/v1/goals/{goal['id']}/book",
        json={
            "title": "達人プログラマー",
            "total_pages": 300,
            "start_date": TODAY.isoformat(),
            "due_date": (TODAY + dt.timedelta(days=30)).isoformat(),
        },
    ).json()
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text

    body = client.get("/api/v1/dashboard").json()

    assert len(body["goal_cards"]) == 1
    card = body["goal_cards"][0]
    assert card["category"] == "READING"
    assert card["remaining_days"] == 30
    assert card["forecast_deviation_days"] is None
    assert card["has_warning"] is False
    assert card["book"]["id"] == book["id"]
    assert card["book"]["title"] == "達人プログラマー"
    assert card["book"]["current_streak"] == 0


def test_dashboard_work_goal_card_shows_work_assignment_progress(client, seeded_session):
    """仕事目標のカードは日次ノルマ等を対象外のまま、work_assignmentの派生値
    （経過日数・連続記録日数・直近の月次報告有無）を表示する（要件定義書R-74、
    実装フェーズ分割計画書Phase23）。"""
    goal = client.post(
        "/api/v1/goals",
        json={"category": "WORK", "name": "仕事目標A", "start_date": TODAY.isoformat()},
    ).json()
    work_assignment = client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment",
        json={
            "client_name": "A社",
            "expected_content": "想定業務内容",
            "start_date": TODAY.isoformat(),
        },
    ).json()
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text

    body = client.get("/api/v1/dashboard").json()

    assert len(body["goal_cards"]) == 1
    card = body["goal_cards"][0]
    assert card["category"] == "WORK"
    assert card["progress_rate"] is None
    assert card["remaining_days"] is None
    assert card["forecast_deviation_days"] is None
    assert card["has_warning"] is False
    assert card["work_assignment"]["id"] == work_assignment["id"]
    assert card["work_assignment"]["client_name"] == "A社"
    assert card["work_assignment"]["elapsed_days"] == 0


def test_goal_remaining_days_none_when_no_exam_subjects():
    """境界値: 試験科目未登録の目標でも例外が発生しないこと。"""
    goal = Goal(name="科目未登録", start_date=TODAY, status=GoalStatus.ACTIVE)

    assert _goal_remaining_days(goal, TODAY) is None
