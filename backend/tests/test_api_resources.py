"""リソーススロット・曜日別既定値・配分状況APIのテスト（データ構造編6.2、仕様書6.3・10章）。"""


def _create_slot(
    client,
    name="通勤",
    start_time="07:00:00",
    end_time="08:00:00",
    environment="MOBILE",
    weekdays=None,
):
    payload = {
        "name": name,
        "start_time": start_time,
        "end_time": end_time,
        "environment": environment,
        "weekdays": weekdays if weekdays is not None else [0, 1, 2, 3, 4],
    }
    return client.post("/api/v1/resources/slots", json=payload)


def test_create_and_list_slot(client):
    response = _create_slot(client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["duration_hours"] == 1.0
    assert body["weekdays"] == [0, 1, 2, 3, 4]

    listed = client.get("/api/v1/resources/slots")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_create_slot_rejects_start_after_end(client):
    response = _create_slot(client, start_time="08:00:00", end_time="07:00:00")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_slot_rejects_environment_any(client):
    response = _create_slot(client, environment="ANY")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_slot_rejects_invalid_weekday(client):
    response = _create_slot(client, weekdays=[7])
    assert response.status_code == 400


def test_update_and_delete_slot(client):
    created = _create_slot(client).json()

    updated = client.patch(
        f"/api/v1/resources/slots/{created['id']}", json={"name": "始業前", "is_active": False}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "始業前"
    assert updated.json()["is_active"] is False

    deleted = client.delete(f"/api/v1/resources/slots/{created['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/v1/resources/slots").json() == []


def test_update_slot_weekdays_only(client):
    created = _create_slot(client).json()

    updated = client.patch(f"/api/v1/resources/slots/{created['id']}", json={"weekdays": [5, 6]})
    assert updated.status_code == 200
    assert updated.json()["weekdays"] == [5, 6]
    # name・is_active は未指定のため変更されない。
    assert updated.json()["name"] == created["name"]
    assert updated.json()["is_active"] is True


def test_update_missing_slot_returns_404(client):
    response = client.patch("/api/v1/resources/slots/9999", json={"name": "x"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_day_type_defaults_get_and_put(client):
    defaults = client.get("/api/v1/resources/day-type-defaults")
    assert defaults.status_code == 200
    assert defaults.json()["5"] == "BUFFER"

    updated = client.put("/api/v1/resources/day-type-defaults", json={"5": "PLAN"})
    assert updated.status_code == 200
    assert updated.json()["5"] == "PLAN"


def test_day_type_defaults_rejects_off(client):
    response = client.put("/api/v1/resources/day-type-defaults", json={"0": "OFF"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_day_type_defaults_rejects_out_of_range_weekday(client):
    response = client.put("/api/v1/resources/day-type-defaults", json={"9": "PLAN"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_day_type_defaults_inserts_missing_weekday_row(client, seeded_session):
    from app.models.setting import DayTypeDefault

    seeded_session.query(DayTypeDefault).filter(DayTypeDefault.weekday == 3).delete()
    seeded_session.flush()

    response = client.put("/api/v1/resources/day-type-defaults", json={"3": "BUFFER"})
    assert response.status_code == 200
    assert response.json()["3"] == "BUFFER"


def test_allocation_reports_per_slot_minutes(client):
    """配分状況はスロットごとに、目標別の配分分数と残り時間を返す（仕様書6.3）。"""
    slot = _create_slot(client, weekdays=[0, 1, 2, 3, 4, 5, 6]).json()

    goal = client.post("/api/v1/goals", json={"name": "目標A", "start_date": "2026-01-01"}).json()
    client.put(
        f"/api/v1/goals/{goal['id']}/slot-allocations",
        json={"allocations": [{"slot_id": slot["id"], "minutes": 24}]},
    )
    client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "RANGE",
            "exam_date_from": "2026-06-01",
            "exam_date_to": "2026-06-10",
        },
    )
    subject_id = client.get(f"/api/v1/goals/{goal['id']}").json()["exam_subjects"][0]["id"]
    client.post(
        f"/api/v1/goals/{goal['id']}/materials",
        json={
            "name": "教材A",
            "unit_label": "ページ",
            "total_amount": 100,
            "planned_cycles": 1,
            "subject_ids": [subject_id],
            "start_date": "2026-01-01",
            "due_date_is_manual": False,
        },
    )
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text

    allocation = client.get("/api/v1/resources/allocation")
    assert allocation.status_code == 200
    body = allocation.json()
    assert body["slots"] == [
        {
            "slot_id": slot["id"],
            "slot_name": slot["name"],
            "duration_minutes": 60,
            "allocated_minutes": 24,
            "unallocated_minutes": 36,
            "is_over_capacity": False,
            "goal_allocations": [{"goal_id": goal["id"], "goal_name": "目標A", "minutes": 24}],
        }
    ]
    assert body["total_hours_by_weekday"]["0"] == 1.0
    assert body["total_hours_by_environment"]["MOBILE"] == 7.0


def test_day_boundary_hour_get_and_put(client):
    initial = client.get("/api/v1/resources/day-boundary-hour")
    assert initial.status_code == 200
    assert initial.json() == {"day_boundary_hour": 0}

    updated = client.put("/api/v1/resources/day-boundary-hour", json={"day_boundary_hour": 4})
    assert updated.status_code == 200
    assert updated.json() == {"day_boundary_hour": 4}

    confirmed = client.get("/api/v1/resources/day-boundary-hour")
    assert confirmed.json() == {"day_boundary_hour": 4}


def test_day_boundary_hour_rejects_out_of_range(client):
    response = client.put("/api/v1/resources/day-boundary-hour", json={"day_boundary_hour": 12})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_holiday_treat_as_buffer_get_and_put(client):
    initial = client.get("/api/v1/resources/holiday-treat-as-buffer")
    assert initial.status_code == 200
    assert initial.json() == {"treat_as_buffer": True}

    updated = client.put(
        "/api/v1/resources/holiday-treat-as-buffer", json={"treat_as_buffer": False}
    )
    assert updated.status_code == 200
    assert updated.json() == {"treat_as_buffer": False}

    confirmed = client.get("/api/v1/resources/holiday-treat-as-buffer")
    assert confirmed.json() == {"treat_as_buffer": False}


def test_shortening_slot_is_allowed_and_reported_as_over_capacity(client):
    """配分済みのスロットを短縮しても保存は許容し、超過として報告すること（仕様書NT-09）。

    生活の変化（通勤時間の短縮等）を先に登録できないと本末転倒になるため、拒否ではなく
    警告とする（要件定義書R-87）。
    """
    slot = _create_slot(client, weekdays=[0, 1, 2, 3, 4, 5, 6]).json()  # 07:00-08:00 = 60分
    goal = client.post("/api/v1/goals", json={"name": "目標A", "start_date": "2026-01-01"}).json()
    client.put(
        f"/api/v1/goals/{goal['id']}/slot-allocations",
        json={"allocations": [{"slot_id": slot["id"], "minutes": 60}]},
    )
    client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "RANGE",
            "exam_date_from": "2026-06-01",
            "exam_date_to": "2026-06-10",
        },
    )
    subject_id = client.get(f"/api/v1/goals/{goal['id']}").json()["exam_subjects"][0]["id"]
    client.post(
        f"/api/v1/goals/{goal['id']}/materials",
        json={
            "name": "教材A",
            "unit_label": "ページ",
            "total_amount": 100,
            "planned_cycles": 1,
            "subject_ids": [subject_id],
            "start_date": "2026-01-01",
            "due_date_is_manual": False,
        },
    )
    assert client.post(f"/api/v1/goals/{goal['id']}/activate").status_code == 200

    shortened = client.patch(f"/api/v1/resources/slots/{slot['id']}", json={"end_time": "07:30:00"})
    assert shortened.status_code == 200, shortened.text

    status = client.get("/api/v1/resources/allocation").json()["slots"][0]
    assert status["duration_minutes"] == 30
    assert status["allocated_minutes"] == 60
    assert status["unallocated_minutes"] == -30
    assert status["is_over_capacity"] is True

    rows = client.get(f"/api/v1/goals/{goal['id']}/slot-allocations").json()
    assert [row["is_over_capacity"] for row in rows] == [True]


def test_deleting_allocated_slot_removes_allocation_without_error(client):
    """配分済みのスロットを削除できること（配分はCASCADEで消える。要件定義書R-87）。"""
    slot = _create_slot(client, weekdays=[0]).json()
    goal = client.post("/api/v1/goals", json={"name": "目標A", "start_date": "2026-01-01"}).json()
    client.put(
        f"/api/v1/goals/{goal['id']}/slot-allocations",
        json={"allocations": [{"slot_id": slot["id"], "minutes": 30}]},
    )

    deleted = client.delete(f"/api/v1/resources/slots/{slot['id']}")

    assert deleted.status_code == 204
    assert client.get(f"/api/v1/goals/{goal['id']}/slot-allocations").json() == []
