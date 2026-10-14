"""日次記録APIのテストのうち、カテゴリを問わない共通のエンドポイント（本日取得・コメント等）
とカテゴリ横断の相互独立性（データ構造編6.2、仕様書6.4〜6.7・7.2章、実装フェーズ分割計画書
Phase4・Phase5・S02）。カテゴリ固有のエンドポイントのテストはtest_api_records_exam.py・
_reading.py・_work.pyを参照（実装フェーズ分割計画書S02、test_api_records.pyからの分割）。
`api/records.py`自体は分割しない（§1.5）。
"""

import datetime as dt
import json
from pathlib import Path

from app.constants.domain import CONTEXT_CATEGORIES_BY_PURPOSE
from tests import api_allocation_helpers


def _create_goal_with_subject(
    client, exam_date_from="2026-06-01", exam_date_to="2026-06-10", name="目標A"
):
    goal = client.post("/api/v1/goals", json={"name": name, "start_date": "2026-01-01"}).json()
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


def _make_active_goal_with_material(client, goal_name="目標A", **material_overrides):
    goal, subject_id = _create_goal_with_subject(client, name=goal_name)
    material = _create_material(client, goal["id"], [subject_id], **material_overrides)
    api_allocation_helpers.allocate(client, goal["id"])
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text
    return goal, material


def _make_active_reading_goal_with_book(client):
    goal = client.post(
        "/api/v1/goals",
        json={"category": "READING", "name": "読書目標A", "start_date": "2026-01-01"},
    ).json()
    book = client.post(
        f"/api/v1/goals/{goal['id']}/book",
        json={
            "title": "書籍A",
            "total_pages": 300,
            "start_date": "2026-01-01",
            "due_date": "2026-12-31",
        },
    ).json()
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text
    return goal, book


def _make_active_work_goal_with_assignment(client):
    goal = client.post(
        "/api/v1/goals",
        json={"category": "WORK", "name": "仕事目標A", "start_date": "2026-01-01"},
    ).json()
    work_assignment = client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment",
        json={"expected_content": "想定業務内容", "start_date": "2026-01-01"},
    ).json()
    activated = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert activated.status_code == 200, activated.text
    return goal, work_assignment


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
    assert body["exam_record_state"] is None
    assert body["reading_record_state"] is None
    assert body["work_record_state"] is None
    assert body["study_logs"] == []
    assert body["comments"] == []
    assert body["diary_entries"] == []


# --- POST /records/{date}/progress（カテゴリを問わない共通の入力検証） ---


def test_register_progress_endpoint_rejects_both_lists_empty(client):
    target = dt.date.today().isoformat()

    response = client.post(f"/api/v1/records/{target}/progress", json={})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- カテゴリ横断の相互独立性（仕様変更2026-09-05） ---


def test_finalize_reading_endpoint_does_not_block_exam_finalize(client):
    """読書を確定した後でも、資格勉強の/finalizeは引き続き成功する
    （仕様変更2026-09-05のコア要件）。"""
    goal, material = _make_active_goal_with_material(client)
    _, book = _make_active_reading_goal_with_book(client)
    target = dt.date.today().isoformat()

    reading_response = client.post(
        f"/api/v1/records/{target}/reading-finalize",
        json={"reading_logs": [{"book_id": book["id"], "recall_body": "読了に向けた想起"}]},
    )
    assert reading_response.status_code == 200, reading_response.text

    exam_response = client.post(
        f"/api/v1/records/{target}/finalize",
        json={
            "study_logs": [
                {
                    "material_id": material["id"],
                    "slot_minutes": api_allocation_helpers.slot_minutes_payload(client, 30),
                    "amount_completed": 10,
                }
            ],
            "diary_entries": [
                {"goal_id": goal["id"], "diary_body": "所感", "diary_learned": "学び"}
            ],
        },
    )

    assert exam_response.status_code == 200, exam_response.text
    body = exam_response.json()
    assert body["exam_record_state"] == "REPORTED"
    assert body["reading_record_state"] == "REPORTED"


def test_finalize_work_endpoint_does_not_block_exam_and_reading_finalize(client):
    """仕事を確定した後でも、読書・資格勉強の確定は引き続き成功する
    （カテゴリごとに独立して確定する仕様変更2026-09-05のコア要件。
    test_finalize_reading_endpoint_does_not_block_exam_finalizeの仕事版）。

    1カテゴリだけ確定した日は集約値（record_state）が報告済となるため、以前は画面の遷移先
    判定がこれを見て閲覧画面へ誘導し、残るカテゴリを報告する手段が失われていた
    （1.1（改20）で是正）。APIは当初から確定できるが、報告された症状そのものの形で固定する。
    """
    exam_goal, material = _make_active_goal_with_material(client)
    _reading_goal, book = _make_active_reading_goal_with_book(client)
    _work_goal, work_assignment = _make_active_work_goal_with_assignment(client)
    target = dt.date.today().isoformat()

    work_response = client.post(
        f"/api/v1/records/{target}/work-finalize",
        json={"work_logs": [{"work_assignment_id": work_assignment["id"], "body": "業務内容A"}]},
    )
    assert work_response.status_code == 200, work_response.text
    after_work = work_response.json()
    assert after_work["work_record_state"] == "REPORTED"
    assert after_work["exam_record_state"] is None
    assert after_work["reading_record_state"] is None

    reading_response = client.post(
        f"/api/v1/records/{target}/reading-finalize",
        json={"reading_logs": [{"book_id": book["id"], "recall_body": "読了に向けた想起"}]},
    )
    assert reading_response.status_code == 200, reading_response.text

    exam_response = client.post(
        f"/api/v1/records/{target}/finalize",
        json={
            "study_logs": [
                {
                    "material_id": material["id"],
                    "slot_minutes": api_allocation_helpers.slot_minutes_payload(client, 30),
                    "amount_completed": 10,
                }
            ],
            "diary_entries": [
                {"goal_id": exam_goal["id"], "diary_body": "所感", "diary_learned": "学び"}
            ],
        },
    )
    assert exam_response.status_code == 200, exam_response.text
    finalized = exam_response.json()
    assert finalized["exam_record_state"] == "REPORTED"
    assert finalized["reading_record_state"] == "REPORTED"
    assert finalized["work_record_state"] == "REPORTED"


# --- コメント ---


def test_comment_create_update_delete_flow(client):
    """コメントは実行中の目標が存在する間のみ操作できる（開発Todo 1-7、未決事項の既定値）。"""
    _make_active_reading_goal_with_book(client)
    target = dt.date.today().isoformat()
    client.post(
        f"/api/v1/records/{target}/finalize",
        json={"study_logs": [], "diary_entries": []},
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
    _make_active_reading_goal_with_book(client)
    target = dt.date.today().isoformat()
    response = client.post(f"/api/v1/records/{target}/comments", json={"body": "コメント"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_update_missing_comment_returns_404(client):
    response = client.patch("/api/v1/comments/9999", json={"body": "x"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- 「AIが参照した情報」表示（context_categories、2026-09-19） ---


def test_every_context_category_has_a_frontend_message():
    """`CONTEXT_CATEGORIES_BY_PURPOSE`が返しうる値すべてに画面文言があること
    （test_api_errors.pyのreason版・横断チェック）。文言が無いカテゴリは
    `t()`が未解決時にキー文字列をそのまま返す仕様（frontend/src/locales/t.ts）のため、
    「dailyReport.chat.contextCategories.MATERIAL_PROGRESS」のような生のキーが
    画面にそのまま表示されてしまう。
    """
    categories = {
        category for values in CONTEXT_CATEGORIES_BY_PURPOSE.values() for category in values
    }
    locale_path = Path(__file__).resolve().parents[2] / "frontend" / "src" / "locales" / "ja.json"
    messages = json.loads(locale_path.read_text(encoding="utf-8"))["dailyReport"]["chat"][
        "contextCategories"
    ]
    missing = sorted(categories - set(messages))
    assert missing == [], (
        f"ja.json の dailyReport.chat.contextCategories.* に文言が無いカテゴリ: {missing}"
    )
    stale = sorted(set(messages) - categories)
    assert stale == [], f"バックエンドが返さないカテゴリの文言が残っている: {stale}"
