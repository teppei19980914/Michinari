"""目標・試験科目・負荷プロファイルAPIのテスト（データ構造編5.3・6.2、仕様書6.2・7.1・7.3・10章）。"""

import datetime as dt

from app.models.record import DailyRecord, StudyLog


def _create_goal(client, name="目標A", start_date="2026-01-01", resource_ratio=None):
    goal = client.post("/api/v1/goals", json={"name": name, "start_date": start_date}).json()
    if resource_ratio is not None:
        client.patch(f"/api/v1/goals/{goal['id']}", json={"resource_ratio": resource_ratio})
    return goal


def _add_subject(
    client, goal_id, name="科目A", exam_date_from="2026-06-01", exam_date_to="2026-06-10"
):
    response = client.post(
        f"/api/v1/goals/{goal_id}/subjects",
        json={
            "name": name,
            "exam_date_type": "RANGE",
            "exam_date_from": exam_date_from,
            "exam_date_to": exam_date_to,
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


def _make_activatable_goal(client, resource_ratio):
    goal = _create_goal(client, resource_ratio=resource_ratio)
    subject = _add_subject(client, goal["id"])
    _add_material(client, goal["id"], [subject["id"]])
    return goal


# --- 目標 基本CRUD ---


def test_create_list_get_goal(client):
    goal = _create_goal(client)
    assert goal["status"] == "DRAFT"
    assert goal["resource_ratio"] == 0.0

    listed = client.get("/api/v1/goals").json()
    assert len(listed) == 1

    detail = client.get(f"/api/v1/goals/{goal['id']}").json()
    assert detail["exam_subjects"] == []
    assert detail["materials"] == []
    assert detail["load_profiles"] == []


def test_get_missing_goal_returns_404(client):
    response = client.get("/api/v1/goals/9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_delete_draft_goal_succeeds(client):
    goal = _create_goal(client)
    response = client.delete(f"/api/v1/goals/{goal['id']}")
    assert response.status_code == 204


def test_delete_non_draft_goal_is_rejected(client):
    goal = _make_activatable_goal(client, resource_ratio=0.3)
    client.post(f"/api/v1/goals/{goal['id']}/activate")

    response = client.delete(f"/api/v1/goals/{goal['id']}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


# --- 状態遷移 ---


def test_activate_requires_subject_and_material(client):
    goal = _create_goal(client, resource_ratio=0.3)
    response = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EXAM_SUBJECT_REQUIRED"


def test_activate_records_initial_baseline(client):
    goal = _make_activatable_goal(client, resource_ratio=0.3)
    response = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACTIVE"

    baselines = client.get(f"/api/v1/goals/{goal['id']}/baselines").json()
    reasons = [b["reason"] for b in baselines]
    assert "INITIAL" in reasons


def test_activate_twice_is_rejected(client):
    goal = _make_activatable_goal(client, resource_ratio=0.3)
    client.post(f"/api/v1/goals/{goal['id']}/activate")

    response = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_activate_rejects_resource_ratio_over_100_percent(client):
    goal_a = _make_activatable_goal(client, resource_ratio=0.7)
    client.post(f"/api/v1/goals/{goal_a['id']}/activate")

    goal_b = _make_activatable_goal(client, resource_ratio=0.4)
    response = client.post(f"/api/v1/goals/{goal_b['id']}/activate")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RESOURCE_EXCEEDED"


def test_patch_active_goal_rejects_resource_ratio_over_100_percent(client):
    goal_a = _make_activatable_goal(client, resource_ratio=0.6)
    client.post(f"/api/v1/goals/{goal_a['id']}/activate")
    goal_b = _make_activatable_goal(client, resource_ratio=0.2)
    client.post(f"/api/v1/goals/{goal_b['id']}/activate")

    response = client.patch(f"/api/v1/goals/{goal_b['id']}", json={"resource_ratio": 0.5})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RESOURCE_EXCEEDED"


def test_pause_then_resume(client):
    goal = _make_activatable_goal(client, resource_ratio=0.3)
    client.post(f"/api/v1/goals/{goal['id']}/activate")

    paused = client.post(f"/api/v1/goals/{goal['id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "PAUSED"

    resumed = client.post(f"/api/v1/goals/{goal['id']}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "ACTIVE"


def test_resume_rejects_when_resource_capacity_insufficient(client):
    goal_a = _make_activatable_goal(client, resource_ratio=0.5)
    client.post(f"/api/v1/goals/{goal_a['id']}/activate")
    client.post(f"/api/v1/goals/{goal_a['id']}/pause")

    goal_b = _make_activatable_goal(client, resource_ratio=0.8)
    client.post(f"/api/v1/goals/{goal_b['id']}/activate")

    response = client.post(f"/api/v1/goals/{goal_a['id']}/resume")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RESOURCE_EXCEEDED"


def test_resume_requires_resource_ratio_to_be_set(client):
    """一時停止中にリソース配分を0へ変更した場合、復帰時に再検出して拒否する(activate_goalと同じ
    横展開先。一時停止中はACTIVEでないため、update_goalの合計超過チェックをすり抜けて0へ変更でき
    てしまうため、resume_goal側でも起点未設定を検証する)。"""
    goal = _make_activatable_goal(client, resource_ratio=0.3)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    client.post(f"/api/v1/goals/{goal['id']}/pause")
    client.patch(f"/api/v1/goals/{goal['id']}", json={"resource_ratio": 0})

    response = client.post(f"/api/v1/goals/{goal['id']}/resume")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RESOURCE_RATIO_REQUIRED"


def test_close_without_confirmation_is_rejected_then_succeeds_with_confirmation(client):
    goal = _make_activatable_goal(client, resource_ratio=0.3)
    client.post(f"/api/v1/goals/{goal['id']}/activate")

    rejected = client.post(f"/api/v1/goals/{goal['id']}/close", json={})
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    closed = client.post(f"/api/v1/goals/{goal['id']}/close", json={"confirm_without_result": True})
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED_WITHOUT_RESULT"


def test_update_closed_goal_is_rejected(client):
    goal = _make_activatable_goal(client, resource_ratio=0.3)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    client.post(f"/api/v1/goals/{goal['id']}/close", json={"confirm_without_result": True})

    response = client.patch(f"/api/v1/goals/{goal['id']}", json={"memo": "更新"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_add_subject_to_closed_goal_is_rejected(client):
    goal = _make_activatable_goal(client, resource_ratio=0.3)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    client.post(f"/api/v1/goals/{goal['id']}/close", json={"confirm_without_result": True})

    response = client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "追加科目",
            "exam_date_type": "RANGE",
            "exam_date_from": "2026-08-01",
            "exam_date_to": "2026-08-10",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


# --- 試験科目 ---


def test_create_subject_rejects_range_from_after_to(client):
    goal = _create_goal(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "RANGE",
            "exam_date_from": "2026-06-10",
            "exam_date_to": "2026-06-01",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_subject_fixed_requires_exam_date_fixed(client):
    goal = _create_goal(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={"name": "科目A", "exam_date_type": "FIXED"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_delete_subject(client):
    goal = _create_goal(client)
    subject = _add_subject(client, goal["id"])
    response = client.delete(f"/api/v1/subjects/{subject['id']}")
    assert response.status_code == 204


def test_fix_exam_date_recalculates_due_date_and_records_baseline(client):
    goal = _create_goal(client)
    subject = _add_subject(
        client, goal["id"], exam_date_from="2026-06-01", exam_date_to="2026-06-10"
    )
    material = _add_material(client, goal["id"], [subject["id"]])
    assert material["due_date"] == "2026-05-31"

    response = client.post(
        f"/api/v1/subjects/{subject['id']}/fix-date", json={"exam_date_fixed": "2026-07-01"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["exam_date_type"] == "FIXED"

    updated_goal = client.get(f"/api/v1/goals/{goal['id']}").json()
    assert updated_goal["materials"][0]["due_date"] == "2026-06-30"

    baselines = client.get(f"/api/v1/goals/{goal['id']}/baselines").json()
    reasons = [b["reason"] for b in baselines]
    assert "EXAM_DATE_FIXED" in reasons


def test_fix_exam_date_on_closed_goal_is_rejected(client):
    goal = _make_activatable_goal(client, resource_ratio=0.3)
    subject_id = client.get(f"/api/v1/goals/{goal['id']}").json()["exam_subjects"][0]["id"]
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    client.post(f"/api/v1/goals/{goal['id']}/close", json={"confirm_without_result": True})

    response = client.post(
        f"/api/v1/subjects/{subject_id}/fix-date", json={"exam_date_fixed": "2026-07-01"}
    )
    assert response.status_code == 409


# --- 負荷プロファイル ---


def test_create_load_profile(client):
    goal = _create_goal(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/load-profiles",
        json={
            "date_from": "2026-03-01",
            "date_to": "2026-03-31",
            "coefficient": 0.5,
            "note": "繁忙期",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["coefficient"] == 0.5


def test_create_load_profile_rejects_overlap(client):
    goal = _create_goal(client)
    client.post(
        f"/api/v1/goals/{goal['id']}/load-profiles",
        json={"date_from": "2026-03-01", "date_to": "2026-03-31", "coefficient": 0.5, "note": None},
    )
    response = client.post(
        f"/api/v1/goals/{goal['id']}/load-profiles",
        json={"date_from": "2026-03-15", "date_to": "2026-04-15", "coefficient": 0.8, "note": None},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_load_profile_rejects_non_positive_coefficient(client):
    goal = _create_goal(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/load-profiles",
        json={"date_from": "2026-03-01", "date_to": "2026-03-31", "coefficient": 0, "note": None},
    )
    assert response.status_code == 400


def test_update_goal_name_start_date_and_memo(client):
    goal = _create_goal(client)
    response = client.patch(
        f"/api/v1/goals/{goal['id']}",
        json={"name": "改名後", "start_date": "2026-02-01", "memo": "メモ"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "改名後"
    assert body["start_date"] == "2026-02-01"
    assert body["memo"] == "メモ"


def test_activate_requires_material_even_with_subject(client):
    goal = _create_goal(client, resource_ratio=0.3)
    _add_subject(client, goal["id"])
    response = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MATERIAL_REQUIRED"


def test_activate_requires_resource_ratio_to_be_set(client):
    """仕様書7.1「下書き→進行中」の遷移条件「リソース配分が設定済み」を満たさない場合は拒否する。

    resource_ratio未設定(既定値0)のまま開始すると、slot_service.allocate_dayが常に0時間を
    配分し続け、完了予測・強制リプラン判定(NT-02)が恒久的に機能しなくなるため、開始前に検出する。
    """
    goal = _make_activatable_goal(client, resource_ratio=0)
    response = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RESOURCE_RATIO_REQUIRED"


def test_activate_skips_baseline_for_inactive_material(client):
    goal = _make_activatable_goal(client, resource_ratio=0.3)
    material = client.get(f"/api/v1/goals/{goal['id']}").json()["materials"][0]
    client.post(f"/api/v1/materials/{material['id']}/deactivate")

    response = client.post(f"/api/v1/goals/{goal['id']}/activate")
    assert response.status_code == 200, response.text
    # 教材作成時点でMATERIAL_CHANGEDは記録済みだが、無効化された教材にはINITIALが追加されない。
    reasons = [b["reason"] for b in client.get(f"/api/v1/goals/{goal['id']}/baselines").json()]
    assert "INITIAL" not in reasons


def test_pause_non_active_goal_is_rejected(client):
    goal = _create_goal(client)
    response = client.post(f"/api/v1/goals/{goal['id']}/pause")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_resume_non_paused_goal_is_rejected(client):
    goal = _create_goal(client)
    response = client.post(f"/api/v1/goals/{goal['id']}/resume")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_close_non_active_goal_is_rejected(client):
    goal = _create_goal(client)
    response = client.post(f"/api/v1/goals/{goal['id']}/close", json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_create_subject_range_missing_dates_is_rejected(client):
    goal = _create_goal(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={"name": "科目A", "exam_date_type": "RANGE"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_subject_fixed_type_succeeds(client):
    goal = _create_goal(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={"name": "科目A", "exam_date_type": "FIXED", "exam_date_fixed": "2026-07-01"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["exam_date_type"] == "FIXED"


def test_update_subject_passing_score(client):
    goal = _create_goal(client)
    subject = _add_subject(client, goal["id"])
    response = client.patch(f"/api/v1/subjects/{subject['id']}", json={"passing_score": 70})
    assert response.status_code == 200
    assert response.json()["passing_score"] == 70
    assert response.json()["passing_score_type"] == "PERCENTAGE"


def test_create_subject_with_raw_score_passing_score(client):
    goal = _create_goal(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "FIXED",
            "exam_date_fixed": "2026-07-01",
            "passing_score": 700,
            "passing_score_type": "RAW_SCORE",
            "passing_score_max": 1000,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["passing_score"] == 700
    assert body["passing_score_type"] == "RAW_SCORE"
    assert body["passing_score_max"] == 1000


def test_create_subject_rejects_raw_score_without_max(client):
    goal = _create_goal(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "FIXED",
            "exam_date_fixed": "2026-07-01",
            "passing_score": 700,
            "passing_score_type": "RAW_SCORE",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_subject_rejects_raw_score_exceeding_max(client):
    goal = _create_goal(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "FIXED",
            "exam_date_fixed": "2026-07-01",
            "passing_score": 1100,
            "passing_score_type": "RAW_SCORE",
            "passing_score_max": 1000,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_missing_subject_returns_404(client):
    response = client.patch("/api/v1/subjects/9999", json={"name": "x"})
    assert response.status_code == 404


def test_update_subject_name_only(client):
    goal = _create_goal(client)
    subject = _add_subject(client, goal["id"])
    response = client.patch(f"/api/v1/subjects/{subject['id']}", json={"name": "改名科目"})
    assert response.status_code == 200
    assert response.json()["name"] == "改名科目"
    # 有効受験日が変わらない更新ではリプラン履歴が発生しない（データ構造編5.3）。
    assert client.get(f"/api/v1/goals/{goal['id']}/baselines").json() == []


def test_update_subject_date_change_propagates_to_material_due_date(client):
    goal = _create_goal(client)
    subject = _add_subject(
        client, goal["id"], exam_date_from="2026-06-01", exam_date_to="2026-06-10"
    )
    material = _add_material(client, goal["id"], [subject["id"]])
    assert material["due_date"] == "2026-05-31"

    response = client.patch(
        f"/api/v1/subjects/{subject['id']}", json={"exam_date_from": "2026-05-01"}
    )
    assert response.status_code == 200, response.text

    updated_goal = client.get(f"/api/v1/goals/{goal['id']}").json()
    assert updated_goal["materials"][0]["due_date"] == "2026-04-30"
    reasons = [b["reason"] for b in client.get(f"/api/v1/goals/{goal['id']}/baselines").json()]
    assert "MATERIAL_CHANGED" in reasons


def test_update_subject_date_does_not_affect_manual_due_date_material(client):
    goal = _create_goal(client)
    subject = _add_subject(
        client, goal["id"], exam_date_from="2026-06-01", exam_date_to="2026-06-10"
    )
    manual_material = client.post(
        f"/api/v1/goals/{goal['id']}/materials",
        json={
            "name": "手動締切教材",
            "unit_label": "ページ",
            "total_amount": 100,
            "planned_cycles": 1,
            "subject_ids": [subject["id"]],
            "start_date": "2026-01-01",
            "due_date_is_manual": True,
            "due_date": "2026-12-31",
        },
    ).json()

    client.patch(f"/api/v1/subjects/{subject['id']}", json={"exam_date_from": "2026-05-01"})

    unchanged = client.get(f"/api/v1/materials/{manual_material['id']}/cycles")
    assert unchanged.status_code == 200
    detail = client.get(f"/api/v1/goals/{goal['id']}").json()
    material = next(m for m in detail["materials"] if m["id"] == manual_material["id"])
    assert material["due_date"] == "2026-12-31"


def test_update_subject_date_without_changing_earliest_date_skips_baseline(client):
    goal = _create_goal(client)
    earlier_subject = _add_subject(
        client, goal["id"], name="科目A", exam_date_from="2026-06-01", exam_date_to="2026-06-10"
    )
    later_subject = _add_subject(
        client, goal["id"], name="科目B", exam_date_from="2026-08-01", exam_date_to="2026-08-10"
    )
    material = _add_material(client, goal["id"], [earlier_subject["id"], later_subject["id"]])
    assert material["due_date"] == "2026-05-31"

    # 最早受験日(科目A)より後ろの科目Bの日付を変更しても、締切(最早日-1)は変化しない。
    # exam_date_to(08-10)以前に収まる値へ変更し、期間整合バリデーションには抵触させない。
    response = client.patch(
        f"/api/v1/subjects/{later_subject['id']}", json={"exam_date_from": "2026-08-05"}
    )
    assert response.status_code == 200, response.text

    detail = client.get(f"/api/v1/goals/{goal['id']}").json()
    updated_material = next(m for m in detail["materials"] if m["id"] == material["id"])
    assert updated_material["due_date"] == "2026-05-31"
    # 教材作成時点でMATERIAL_CHANGEDが1件記録済み。締切が変わらない科目更新では増えない。
    baselines = client.get(f"/api/v1/goals/{goal['id']}/baselines").json()
    assert len(baselines) == 1


def test_update_missing_load_profile_returns_404(client):
    response = client.patch("/api/v1/load-profiles/9999", json={"coefficient": 0.5})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_create_load_profile_rejects_from_after_to(client):
    goal = _create_goal(client)
    response = client.post(
        f"/api/v1/goals/{goal['id']}/load-profiles",
        json={"date_from": "2026-03-31", "date_to": "2026-03-01", "coefficient": 0.5, "note": None},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_and_delete_load_profile(client):
    goal = _create_goal(client)
    profile = client.post(
        f"/api/v1/goals/{goal['id']}/load-profiles",
        json={"date_from": "2026-03-01", "date_to": "2026-03-31", "coefficient": 0.5, "note": None},
    ).json()

    updated = client.patch(
        f"/api/v1/load-profiles/{profile['id']}", json={"coefficient": 0.7, "note": "更新後メモ"}
    )
    assert updated.status_code == 200
    assert updated.json()["coefficient"] == 0.7
    assert updated.json()["note"] == "更新後メモ"

    deleted = client.delete(f"/api/v1/load-profiles/{profile['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/goals/{goal['id']}/load-profiles").json() == []


# --- アーカイブ・完全削除（要件定義書R-61〜R-63、仕様書7.1.1、データ構造編4.2） ---


def _close_goal(client, resource_ratio=0.3):
    goal = _make_activatable_goal(client, resource_ratio=resource_ratio)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    client.post(f"/api/v1/goals/{goal['id']}/close", json={"confirm_without_result": True})
    return goal


def test_archive_requires_closed_status(client):
    goal = _create_goal(client)
    response = client.patch(f"/api/v1/goals/{goal['id']}/archive")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_archive_and_unarchive_goal(client):
    goal = _close_goal(client)

    archived = client.patch(f"/api/v1/goals/{goal['id']}/archive")
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived_at"] is not None

    unarchived = client.patch(f"/api/v1/goals/{goal['id']}/unarchive")
    assert unarchived.status_code == 200
    assert unarchived.json()["archived_at"] is None
    assert unarchived.json()["status"] == "CLOSED_WITHOUT_RESULT"


def test_delete_archived_requires_archived_goal(client):
    goal = _close_goal(client)
    response = client.request(
        "DELETE", f"/api/v1/goals/{goal['id']}/archived", json={"cascade_study_logs": True}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_delete_archived_goal_without_cascade_rejects_when_study_logs_remain(
    client, seeded_session
):
    goal = _close_goal(client)
    material_id = client.get(f"/api/v1/goals/{goal['id']}").json()["materials"][0]["id"]
    record = DailyRecord(record_date=dt.date(2026, 1, 5), record_state="PROGRESS_ONLY")
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        StudyLog(
            daily_record_id=record.id, material_id=material_id, amount_completed=1.0, cycle_number=1
        )
    )
    seeded_session.commit()

    client.patch(f"/api/v1/goals/{goal['id']}/archive")
    response = client.request(
        "DELETE", f"/api/v1/goals/{goal['id']}/archived", json={"cascade_study_logs": False}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_delete_archived_goal_with_cascade_removes_goal_and_related_data(client, seeded_session):
    goal = _close_goal(client)
    material_id = client.get(f"/api/v1/goals/{goal['id']}").json()["materials"][0]["id"]
    record = DailyRecord(record_date=dt.date(2026, 1, 5), record_state="PROGRESS_ONLY")
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        StudyLog(
            daily_record_id=record.id, material_id=material_id, amount_completed=1.0, cycle_number=1
        )
    )
    seeded_session.commit()

    client.patch(f"/api/v1/goals/{goal['id']}/archive")
    response = client.request(
        "DELETE", f"/api/v1/goals/{goal['id']}/archived", json={"cascade_study_logs": True}
    )
    assert response.status_code == 204, response.text
    assert client.get(f"/api/v1/goals/{goal['id']}").status_code == 404


def test_delete_archived_goal_without_study_logs_defaults_to_cascade(client):
    """cascade_study_logsを省略した場合は画面の既定(ON)通りTrue扱いになる（仕様書MD-08）。"""
    goal = _close_goal(client)
    client.patch(f"/api/v1/goals/{goal['id']}/archive")
    response = client.request("DELETE", f"/api/v1/goals/{goal['id']}/archived", json={})
    assert response.status_code == 204, response.text


def test_update_load_profile_without_note_keeps_existing_note(client):
    goal = _create_goal(client)
    profile = client.post(
        f"/api/v1/goals/{goal['id']}/load-profiles",
        json={
            "date_from": "2026-03-01",
            "date_to": "2026-03-31",
            "coefficient": 0.5,
            "note": "元メモ",
        },
    ).json()

    updated = client.patch(f"/api/v1/load-profiles/{profile['id']}", json={"coefficient": 0.6})
    assert updated.status_code == 200
    assert updated.json()["note"] == "元メモ"
