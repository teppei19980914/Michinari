"""案件情報・仕事目標APIのテスト（データ構造編5.3・6.2、仕様書6.2・6.10・7.1、
実装フェーズ分割計画書Phase21）。

資格試験目標のAPIテスト（test_api_goals.py）・読書目標のAPIテスト（test_api_books.py）と
対になる、仕事目標（category=WORK）のCRUD・状態遷移・バリデーションのテスト。
work_logsを伴う日次記録テストは、test_api_records.pyと同じ方針でdt.date.today()を
基準に相対日付を用いる（logical_dateは常にシステム日付と一致するため）。
"""

import datetime as dt


def _create_work_goal(client, name="仕事目標A", start_date="2026-01-01"):
    response = client.post(
        "/api/v1/goals",
        json={"category": "WORK", "name": name, "start_date": start_date},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_exam_goal(client, name="資格目標A", start_date="2026-01-01"):
    response = client.post("/api/v1/goals", json={"name": name, "start_date": start_date})
    assert response.status_code == 201, response.text
    return response.json()


def _add_work_assignment(
    client,
    goal_id,
    client_name="取引先A",
    expected_content="想定業務内容",
    start_date="2026-01-01",
):
    payload = {
        "client_name": client_name,
        "expected_content": expected_content,
        "start_date": start_date,
    }
    response = client.post(f"/api/v1/goals/{goal_id}/work-assignment", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _make_activatable_work_goal(client):
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])
    return goal


# --- 目標作成のcategory対応 ---


def test_create_work_goal(client):
    goal = _create_work_goal(client)
    assert goal["category"] == "WORK"
    assert goal["resource_ratio"] == 0.0

    detail = client.get(f"/api/v1/goals/{goal['id']}").json()
    assert detail["exam_subjects"] == []
    assert detail["materials"] == []
    assert detail["work_assignment"] is None


# --- 案件情報の作成 ---


def test_create_work_assignment_succeeds(client):
    goal = _create_work_goal(client)

    work_assignment = _add_work_assignment(
        client, goal["id"], client_name="A社", expected_content="Webサイト改修"
    )

    assert work_assignment["client_name"] == "A社"
    assert work_assignment["expected_content"] == "Webサイト改修"
    assert work_assignment["goal_id"] == goal["id"]
    assert work_assignment["current_streak"] == 0
    assert work_assignment["last_work_date"] is None
    assert work_assignment["has_recent_monthly_report"] is False

    detail = client.get(f"/api/v1/goals/{goal['id']}").json()
    assert detail["work_assignment"]["client_name"] == "A社"


def test_create_work_assignment_client_name_is_optional(client):
    goal = _create_work_goal(client)

    response = client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment",
        json={"expected_content": "想定業務内容", "start_date": "2026-01-01"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["client_name"] is None


def test_create_second_work_assignment_is_rejected(client):
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])

    response = client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment",
        json={"expected_content": "2件目", "start_date": "2026-01-01"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WORK_ASSIGNMENT_ALREADY_EXISTS"


def test_create_work_assignment_on_exam_goal_is_rejected(client):
    goal = _create_exam_goal(client)

    response = client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment",
        json={"expected_content": "想定業務内容", "start_date": "2026-01-01"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- 案件情報の更新（目標配下のネストパスに統一。書籍と異なりPATCHも
# --- /goals/{id}/work-assignment） ---


def test_update_work_assignment_succeeds(client):
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])

    response = client.patch(
        f"/api/v1/goals/{goal['id']}/work-assignment",
        json={"expected_content": "更新後の想定業務内容", "client_name": "B社"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["expected_content"] == "更新後の想定業務内容"
    assert body["client_name"] == "B社"


def test_update_work_assignment_start_date_only(client):
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"], start_date="2026-01-01")

    response = client.patch(
        f"/api/v1/goals/{goal['id']}/work-assignment", json={"start_date": "2026-02-01"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["start_date"] == "2026-02-01"


def test_update_work_assignment_clears_client_name_with_explicit_null(client):
    """NULL許容列は明示的なnullで空へ戻せる（未指定との区別、constants/sentinels.py）。"""
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])
    client.patch(f"/api/v1/goals/{goal['id']}/work-assignment", json={"client_name": "B社"})

    response = client.patch(
        f"/api/v1/goals/{goal['id']}/work-assignment", json={"client_name": None}
    )

    assert response.status_code == 200, response.text
    assert response.json()["client_name"] is None


def test_update_missing_work_assignment_returns_404(client):
    goal = _create_work_goal(client)

    response = client.patch(
        f"/api/v1/goals/{goal['id']}/work-assignment", json={"expected_content": "存在しない"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- 状態遷移 ---


def test_activate_work_goal_requires_work_assignment(client):
    goal = _create_work_goal(client)

    response = client.post(f"/api/v1/goals/{goal['id']}/activate")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_activate_work_goal_succeeds(client):
    goal = _make_activatable_work_goal(client)

    response = client.post(f"/api/v1/goals/{goal['id']}/activate")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACTIVE"


def test_close_work_goal_with_result_true(client):
    """要件定義書R-72：仕事目標は with_result=True で CLOSED_WITH_RESULT（成果を伴う終了）。"""
    goal = _make_activatable_work_goal(client)
    client.post(f"/api/v1/goals/{goal['id']}/activate")

    response = client.post(f"/api/v1/goals/{goal['id']}/close", json={"with_result": True})

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CLOSED_WITH_RESULT"
    assert response.json()["closed_at"] is not None


def test_close_work_goal_without_with_result_is_without_result(client):
    """with_result省略時（既定False）は CLOSED_WITHOUT_RESULT（中止・打ち切り）。"""
    goal = _make_activatable_work_goal(client)
    client.post(f"/api/v1/goals/{goal['id']}/activate")

    response = client.post(f"/api/v1/goals/{goal['id']}/close", json={})

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CLOSED_WITHOUT_RESULT"


def test_close_exam_goal_with_result_true_is_rejected(client):
    """with_resultは仕事目標専用。EXAM/READINGでTrue指定するとVALIDATION_ERROR。"""
    goal = _create_exam_goal(client)
    subject = client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "RANGE",
            "exam_date_from": "2026-06-01",
            "exam_date_to": "2026-06-10",
        },
    ).json()
    client.post(
        f"/api/v1/goals/{goal['id']}/materials",
        json={
            "name": "教材A",
            "unit_label": "ページ",
            "total_amount": 100,
            "planned_cycles": 1,
            "subject_ids": [subject["id"]],
            "start_date": "2026-01-01",
            "due_date_is_manual": False,
        },
    )
    client.patch(f"/api/v1/goals/{goal['id']}", json={"resource_ratio": 1.0})
    client.post(f"/api/v1/goals/{goal['id']}/activate")

    response = client.post(f"/api/v1/goals/{goal['id']}/close", json={"with_result": True})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_work_assignment_on_closed_goal_is_rejected(client):
    goal = _make_activatable_work_goal(client)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    client.post(f"/api/v1/goals/{goal['id']}/close", json={"with_result": True})

    response = client.patch(
        f"/api/v1/goals/{goal['id']}/work-assignment", json={"expected_content": "更新後"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


# --- リソース配分の対象外（要件定義書R-74） ---


def test_work_goal_cannot_set_resource_ratio(client):
    goal = _create_work_goal(client)

    response = client.patch(f"/api/v1/goals/{goal['id']}", json={"resource_ratio": 0.5})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_work_goal_does_not_count_toward_exam_resource_ratio(client):
    """仕事目標はresource_ratioの合計計算に算入されない（要件定義書R-74）。"""
    exam_goal = _create_exam_goal(client)
    client.patch(f"/api/v1/goals/{exam_goal['id']}", json={"resource_ratio": 1.0})
    subject = client.post(
        f"/api/v1/goals/{exam_goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "RANGE",
            "exam_date_from": "2026-06-01",
            "exam_date_to": "2026-06-10",
        },
    ).json()
    client.post(
        f"/api/v1/goals/{exam_goal['id']}/materials",
        json={
            "name": "教材A",
            "unit_label": "ページ",
            "total_amount": 100,
            "planned_cycles": 1,
            "subject_ids": [subject["id"]],
            "start_date": "2026-01-01",
            "due_date_is_manual": False,
        },
    )
    assert client.post(f"/api/v1/goals/{exam_goal['id']}/activate").status_code == 200

    work_goal = _make_activatable_work_goal(client)
    response = client.post(f"/api/v1/goals/{work_goal['id']}/activate")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACTIVE"


def test_work_goal_pause_then_resume_skips_resource_ratio_validation(client):
    goal = _make_activatable_work_goal(client)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    client.post(f"/api/v1/goals/{goal['id']}/pause")

    response = client.post(f"/api/v1/goals/{goal['id']}/resume")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACTIVE"


# --- 日次記録APIのwork_logs対応 ---


def test_register_progress_with_work_log(client):
    goal = _make_activatable_work_goal(client)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    work_assignment_id = client.get(f"/api/v1/goals/{goal['id']}").json()["work_assignment"]["id"]
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/progress",
        json={"work_logs": [{"work_assignment_id": work_assignment_id, "body": "業務内容A"}]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["work_logs"]) == 1
    assert body["work_logs"][0]["body"] == "業務内容A"


def test_finalize_record_with_work_log(client):
    goal = _make_activatable_work_goal(client)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    work_assignment_id = client.get(f"/api/v1/goals/{goal['id']}").json()["work_assignment"]["id"]
    target = dt.date.today().isoformat()

    response = client.post(
        f"/api/v1/records/{target}/work-finalize",
        json={"work_logs": [{"work_assignment_id": work_assignment_id, "body": "業務内容A"}]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["work_record_state"] == "REPORTED"

    progress = client.get(f"/api/v1/goals/{goal['id']}").json()["work_assignment"]
    assert progress["last_work_date"] == target
    assert progress["current_streak"] == 1
