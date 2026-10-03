"""カレンダーAPIのテスト（データ構造編6.2、技術選定書6章、実装フェーズ分割計画書Phase4）。"""


def _holiday_csv_bytes(rows: list[tuple[str, str]]) -> bytes:
    header = "国民の祝日・休日月日,国民の祝日・休日名称"
    lines = [header] + [f"{date_text},{name}" for date_text, name in rows]
    return ("\r\n".join(lines) + "\r\n").encode("cp932")


def test_get_calendar_returns_day_types_for_range(client):
    response = client.get(
        "/api/v1/calendar", params={"date_from": "2026-03-09", "date_to": "2026-03-10"}
    )
    assert response.status_code == 200
    body = response.json()
    assert [day["target_date"] for day in body] == ["2026-03-09", "2026-03-10"]
    assert all(day["record_state"] is None for day in body)


def test_set_and_clear_day_type_override(client):
    target = "2026-04-01"

    set_response = client.put(
        f"/api/v1/calendar/{target}/day-type", json={"day_type": "OFF", "note": "特別休止日"}
    )
    assert set_response.status_code == 200
    assert set_response.json()["day_type"] == "OFF"

    calendar_response = client.get(
        "/api/v1/calendar", params={"date_from": target, "date_to": target}
    )
    assert calendar_response.json()[0]["day_type"] == "OFF"

    clear_response = client.delete(f"/api/v1/calendar/{target}/day-type")
    assert clear_response.status_code == 204

    calendar_after_clear = client.get(
        "/api/v1/calendar", params={"date_from": target, "date_to": target}
    )
    assert calendar_after_clear.json()[0]["day_type"] != "OFF"


def test_clear_day_type_override_missing_returns_404(client):
    response = client.delete("/api/v1/calendar/2026-04-02/day-type")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_import_holidays_endpoint_returns_summary(client):
    content = _holiday_csv_bytes([("2026/1/1", "元日"), ("2026/1/12", "成人の日")])

    response = client.post(
        "/api/v1/calendar/holidays/import",
        files={"file": ("holidays.csv", content, "text/csv")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported_count"] == 2
    assert body["year_from"] == 2026
    assert body["year_to"] == 2026


def test_import_holidays_endpoint_rejects_invalid_encoding(client):
    response = client.post(
        "/api/v1/calendar/holidays/import",
        files={"file": ("holidays.csv", bytes([0x81, 0xFF]), "text/csv")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
