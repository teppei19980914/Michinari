"""チームメンバーAPIのテスト（要件定義書6.11）。

作成は目標配下のネストパス（api/goals.py）、更新・削除・無効化は独立リソースパス
（api/work_members.py）に分かれるため、test_api_work.py（案件情報）とは別ファイルとする。
"""


def _create_work_goal(client, name="仕事目標A", start_date="2026-01-01"):
    response = client.post(
        "/api/v1/goals", json={"category": "WORK", "name": name, "start_date": start_date}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _add_work_assignment(client, goal_id, start_date="2026-01-01"):
    response = client.post(
        f"/api/v1/goals/{goal_id}/work-assignment",
        json={"expected_content": "想定業務内容", "start_date": start_date},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_member(client, goal_id, **overrides):
    payload = {"name": "Aさん"}
    payload.update(overrides)
    response = client.post(f"/api/v1/goals/{goal_id}/work-assignment/members", json=payload)
    return response


# --- 作成 ---


def test_create_member_without_characteristics_succeeds(client):
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])

    response = _create_member(client, goal["id"], name="Aさん")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Aさん"
    assert body["characteristics"] is None
    assert body["consent_confirmed_at"] is None
    assert body["is_active"] is True

    detail = client.get(f"/api/v1/goals/{goal['id']}").json()
    assert len(detail["work_assignment"]["members"]) == 1
    assert detail["work_assignment"]["members"][0]["name"] == "Aさん"


def test_create_member_with_characteristics_without_consent_is_rejected(client):
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])

    response = _create_member(
        client, goal["id"], characteristics="明るい性格", consent_confirmed=False
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_create_member_with_characteristics_and_consent_succeeds(client):
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])

    response = _create_member(
        client,
        goal["id"],
        gender="FEMALE",
        characteristics="明るい性格",
        consent_confirmed=True,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["characteristics"] == "明るい性格"
    assert body["gender"] == "FEMALE"
    assert body["consent_confirmed_at"] is not None


def test_create_member_without_work_assignment_returns_404(client):
    goal = _create_work_goal(client)

    response = _create_member(client, goal["id"])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- 更新 ---


def test_update_member_name(client):
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])
    member = _create_member(client, goal["id"], name="Aさん").json()

    response = client.patch(f"/api/v1/work-members/{member['id']}", json={"name": "Bさん"})

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Bさん"


def test_update_member_characteristics_without_consent_is_rejected(client):
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])
    member = _create_member(client, goal["id"]).json()

    response = client.patch(
        f"/api/v1/work-members/{member['id']}",
        json={"characteristics": "追加した特徴", "consent_confirmed": False},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_update_missing_member_returns_404(client):
    response = client.patch("/api/v1/work-members/999999", json={"name": "Bさん"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- 無効化・削除 ---


def test_deactivate_member(client):
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])
    member = _create_member(client, goal["id"]).json()

    response = client.post(f"/api/v1/work-members/{member['id']}/deactivate")

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False


def test_delete_member_without_reports_succeeds(client):
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])
    member = _create_member(client, goal["id"]).json()

    response = client.delete(f"/api/v1/work-members/{member['id']}")

    assert response.status_code == 204

    detail = client.get(f"/api/v1/goals/{goal['id']}").json()
    assert detail["work_assignment"]["members"] == []


def test_delete_member_with_evaluation_report_is_rejected(client, monkeypatch):
    from app.ai import client as ai_client
    from app.ai import rate_limiter

    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        ai_client,
        "send_message",
        lambda session, *, chat_uid, message: ai_client.SendResult(
            response_text="評価レポート本文", latency_ms=5
        ),
    )
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: "chat-uid",
    )

    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])
    client.patch(f"/api/v1/goals/{goal['id']}/work-assignment", json={"role": "EVALUATOR"})
    member = _create_member(client, goal["id"]).json()
    client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment/evaluation-reports",
        json={"member_id": member["id"], "considerations": "考慮事項"},
    )

    response = client.delete(f"/api/v1/work-members/{member['id']}")

    assert response.status_code == 400
    assert response.json()["error"]["details"] == [{"reason": "WORK_MEMBER_HAS_REPORTS"}]


# --- role（評価者/被評価者） ---


def test_work_assignment_role_defaults_to_null(client):
    goal = _create_work_goal(client)
    work_assignment = _add_work_assignment(client, goal["id"])

    assert work_assignment["role"] is None


def test_set_and_clear_work_assignment_role(client):
    goal = _create_work_goal(client)
    _add_work_assignment(client, goal["id"])

    response = client.patch(
        f"/api/v1/goals/{goal['id']}/work-assignment", json={"role": "EVALUATOR"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "EVALUATOR"

    response = client.patch(f"/api/v1/goals/{goal['id']}/work-assignment", json={"role": None})
    assert response.status_code == 200, response.text
    assert response.json()["role"] is None
