"""受験結果登録・総括レポートAPIのテスト（仕様書6.9 SC-10、6.10、
データ構造編6.2「完了処理とエクスポート」、実装フェーズ分割計画書Phase10）。
"""

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from tests import api_allocation_helpers


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _create_goal(client, name="目標A", start_date="2026-01-01"):
    goal = client.post("/api/v1/goals", json={"name": name, "start_date": start_date}).json()
    api_allocation_helpers.allocate(client, goal["id"])
    return goal


def _add_subject(client, goal_id, name="科目A"):
    response = client.post(
        f"/api/v1/goals/{goal_id}/subjects",
        json={
            "name": name,
            "exam_date_type": "RANGE",
            "exam_date_from": "2026-06-01",
            "exam_date_to": "2026-06-10",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _add_material(client, goal_id, subject_ids, name="教材A"):
    response = client.post(
        f"/api/v1/goals/{goal_id}/materials",
        json={
            "name": name,
            "unit_label": "ページ",
            "total_amount": 100,
            "planned_cycles": 1,
            "subject_ids": subject_ids,
            "start_date": "2026-01-01",
            "due_date_is_manual": False,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _make_active_goal_with_subject(client):
    goal = _create_goal(client)
    subject = _add_subject(client, goal["id"])
    _add_material(client, goal["id"], [subject["id"]])
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    return goal, subject


# --- 受験結果登録 ---


def test_register_exam_result_succeeds(client):
    _, subject = _make_active_goal_with_subject(client)

    response = client.post(
        f"/api/v1/subjects/{subject['id']}/result",
        json={"taken_date": "2026-06-05", "result": "PASS", "score": 85.0},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["subject_id"] == subject["id"]
    assert body["result"] == "PASS"
    assert body["score"] == 85.0


def test_register_exam_result_twice_is_rejected(client):
    _, subject = _make_active_goal_with_subject(client)
    client.post(
        f"/api/v1/subjects/{subject['id']}/result",
        json={"taken_date": "2026-06-05", "result": "PASS"},
    )

    response = client.post(
        f"/api/v1/subjects/{subject['id']}/result",
        json={"taken_date": "2026-06-05", "result": "FAIL"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_register_exam_result_on_closed_goal_is_rejected(client):
    goal, subject = _make_active_goal_with_subject(client)
    client.post(f"/api/v1/goals/{goal['id']}/close", json={"confirm_without_result": True})

    response = client.post(
        f"/api/v1/subjects/{subject['id']}/result",
        json={"taken_date": "2026-06-05", "result": "PASS"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_update_exam_result_succeeds(client):
    _, subject = _make_active_goal_with_subject(client)
    created = client.post(
        f"/api/v1/subjects/{subject['id']}/result",
        json={"taken_date": "2026-06-05", "result": "PENDING"},
    ).json()

    response = client.patch(
        f"/api/v1/results/{created['id']}", json={"result": "PASS", "score": 92.0}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "PASS"
    assert body["score"] == 92.0


def test_update_exam_result_can_change_date_evaluation_and_note(client):
    _, subject = _make_active_goal_with_subject(client)
    created = client.post(
        f"/api/v1/subjects/{subject['id']}/result",
        json={"taken_date": "2026-06-05", "result": "PENDING"},
    ).json()

    response = client.patch(
        f"/api/v1/results/{created['id']}",
        json={"taken_date": "2026-06-06", "evaluation": "A", "note": "落ち着いて解けた"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["taken_date"] == "2026-06-06"
    assert body["evaluation"] == "A"
    assert body["note"] == "落ち着いて解けた"


def test_update_missing_exam_result_returns_404(client):
    response = client.patch("/api/v1/results/9999", json={"result": "PASS"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_all_results_registered_allows_close_with_result(client):
    goal, subject = _make_active_goal_with_subject(client)
    client.post(
        f"/api/v1/subjects/{subject['id']}/result",
        json={"taken_date": "2026-06-05", "result": "PASS"},
    )

    response = client.post(f"/api/v1/goals/{goal['id']}/close", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED_WITH_RESULT"


def test_goal_detail_includes_exam_result_in_subject(client):
    goal, subject = _make_active_goal_with_subject(client)
    client.post(
        f"/api/v1/subjects/{subject['id']}/result",
        json={"taken_date": "2026-06-05", "result": "PASS", "score": 70.0},
    )

    detail = client.get(f"/api/v1/goals/{goal['id']}").json()

    assert detail["exam_subjects"][0]["exam_result"]["result"] == "PASS"
    assert detail["exam_subjects"][0]["exam_result"]["score"] == 70.0


# --- 総括レポート ---


def _stub_send_message(monkeypatch, *, response="総括レポート本文"):
    def _fake(session, *, chat_uid, message):
        return ai_client.SendResult(response_text=response, latency_ms=5)

    monkeypatch.setattr(ai_client, "send_message", _fake)
    counter = iter(range(1000))
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: f"chat-{next(counter)}",
    )


def test_get_retrospective_returns_null_when_not_generated(client):
    goal, _ = _make_active_goal_with_subject(client)

    response = client.get(f"/api/v1/goals/{goal['id']}/retrospective")

    assert response.status_code == 200
    assert response.json() is None


def test_generate_retrospective_creates_and_persists(client, monkeypatch):
    goal, _ = _make_active_goal_with_subject(client)
    _stub_send_message(monkeypatch)

    response = client.post(f"/api/v1/goals/{goal['id']}/retrospective", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["body"] == "総括レポート本文"
    assert body["is_anonymized"] is False

    fetched = client.get(f"/api/v1/goals/{goal['id']}/retrospective").json()
    assert fetched["id"] == body["id"]


def test_regenerate_retrospective_keeps_previous_version(client, monkeypatch):
    goal, _ = _make_active_goal_with_subject(client)
    _stub_send_message(monkeypatch, response="1回目")
    first = client.post(f"/api/v1/goals/{goal['id']}/retrospective", json={}).json()

    _stub_send_message(monkeypatch, response="2回目")
    second = client.post(f"/api/v1/goals/{goal['id']}/retrospective", json={}).json()

    assert first["id"] != second["id"]
    latest = client.get(f"/api/v1/goals/{goal['id']}/retrospective").json()
    assert latest["body"] == "2回目"


def test_generate_anonymized_retrospective_is_separate_from_original(client, monkeypatch):
    goal, _ = _make_active_goal_with_subject(client)
    _stub_send_message(monkeypatch, response="通常版")
    client.post(f"/api/v1/goals/{goal['id']}/retrospective", json={})

    _stub_send_message(monkeypatch, response="匿名化版")
    anon_response = client.post(
        f"/api/v1/goals/{goal['id']}/retrospective", json={"anonymize": True}
    )
    assert anon_response.status_code == 200
    assert anon_response.json()["is_anonymized"] is True

    original = client.get(f"/api/v1/goals/{goal['id']}/retrospective").json()
    anonymized = client.get(
        f"/api/v1/goals/{goal['id']}/retrospective", params={"anonymized": True}
    ).json()
    assert original["body"] == "通常版"
    assert anonymized["body"] == "匿名化版"


# --- 読了レポート（GOAL_RETROSPECTIVE_READING、実装フェーズ分割計画書Phase16） ---


def _make_reading_goal_with_book(client):
    goal = client.post(
        "/api/v1/goals",
        json={"category": "READING", "name": "読書目標A", "start_date": "2026-01-01"},
    ).json()
    book = client.post(
        f"/api/v1/goals/{goal['id']}/book",
        json={
            "title": "達人プログラマー",
            "total_pages": 300,
            "start_date": "2026-01-01",
            "due_date": "2026-12-31",
        },
    ).json()
    return goal, book


def test_generate_retrospective_on_reading_goal_without_book_is_rejected(client, monkeypatch):
    """読了レポートには対象書籍が必須（データ構造編5.3、goal.book is None時のガード）。"""
    goal = client.post(
        "/api/v1/goals",
        json={"category": "READING", "name": "読書目標A", "start_date": "2026-01-01"},
    ).json()
    _stub_send_message(monkeypatch)

    response = client.post(f"/api/v1/goals/{goal['id']}/retrospective", json={})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_generate_retrospective_on_reading_goal_creates_reading_report(client, monkeypatch):
    """読書目標に対する総括レポート生成は、読了レポート（GOAL_RETROSPECTIVE_READING）
    として生成される（Phase16完了条件「読了時に読了レポートが生成・再生成できる」）。"""
    goal, _book = _make_reading_goal_with_book(client)
    _stub_send_message(monkeypatch, response="読了レポート本文")

    response = client.post(f"/api/v1/goals/{goal['id']}/retrospective", json={})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["body"] == "読了レポート本文"

    fetched = client.get(f"/api/v1/goals/{goal['id']}/retrospective").json()
    assert fetched["id"] == body["id"]


def test_generate_retrospective_on_reading_goal_does_not_affect_exam_assistant_settings(
    client, monkeypatch
):
    """読書用の総括レポート生成が資格試験用のプロンプト・アシスタント設定
    （ai.assistant_uid.goal_retrospective）に影響しないこと（Phase16完了条件）。"""
    reading_goal, _book = _make_reading_goal_with_book(client)
    _stub_send_message(monkeypatch, response="読了レポート")
    client.post(f"/api/v1/goals/{reading_goal['id']}/retrospective", json={})

    exam_goal, _subject = _make_active_goal_with_subject(client)
    _stub_send_message(monkeypatch, response="総括レポート")
    exam_response = client.post(f"/api/v1/goals/{exam_goal['id']}/retrospective", json={})

    assert exam_response.status_code == 200, exam_response.text
    assert exam_response.json()["body"] == "総括レポート"
