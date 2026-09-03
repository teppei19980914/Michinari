"""アプリ設定・プロンプトテンプレートAPIのテスト（データ構造編6.2、仕様書6.11）。"""

from app.constants.enums import AiPurpose


def test_get_settings_returns_grouped_defaults(client):
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["ai_connection"]["folder_prefix"] == "ミチナリ"
    assert body["threshold"]["warning_ratio"] == 1.20
    assert body["display"]["default_granularity"] == "WEEK"
    assert body["log"]["retention_days"] == 90


def test_patch_settings_updates_only_specified_group(client):
    response = client.patch(
        "/api/v1/settings",
        json={"ai_connection": {"folder_prefix": "資格試験", "timeout_seconds": 90}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ai_connection"]["folder_prefix"] == "資格試験"
    assert body["ai_connection"]["timeout_seconds"] == 90
    assert body["threshold"]["warning_ratio"] == 1.20

    confirmed = client.get("/api/v1/settings").json()
    assert confirmed["ai_connection"]["folder_prefix"] == "資格試験"


def test_get_settings_includes_reading_assistant_uids_and_recall_window(client):
    """読書用のアシスタント設定・想起注入日数が設定画面（GET/PATCH /settings）から
    変更可能であること（仕様書6.11「全ての設定項目を画面上から変更可能」、Phase16）。"""
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["ai_connection"]["assistant_uid_daily_feedback_reading"] == ""
    assert body["ai_connection"]["assistant_uid_goal_retrospective_reading"] == ""
    assert body["prompt_degradation"]["reading_recall_recent_days"] == 14


def test_patch_settings_updates_reading_assistant_uids_and_recall_window(client):
    response = client.patch(
        "/api/v1/settings",
        json={
            "ai_connection": {
                "assistant_uid_daily_feedback_reading": "uid-daily-reading",
                "assistant_uid_goal_retrospective_reading": "uid-retrospective-reading",
            },
            "prompt_degradation": {"reading_recall_recent_days": 7},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ai_connection"]["assistant_uid_daily_feedback_reading"] == "uid-daily-reading"
    assert (
        body["ai_connection"]["assistant_uid_goal_retrospective_reading"]
        == "uid-retrospective-reading"
    )
    assert body["prompt_degradation"]["reading_recall_recent_days"] == 7


def test_patch_settings_rejects_invalid_theme(client):
    response = client.patch("/api/v1/settings", json={"display": {"theme": "rainbow"}})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_patch_settings_rejects_warning_ratio_not_greater_than_one(client):
    response = client.patch("/api/v1/settings", json={"threshold": {"warning_ratio": 1.0}})
    assert response.status_code == 400


def test_list_prompt_templates_returns_all_purposes(client):
    response = client.get("/api/v1/prompt-templates")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == len(AiPurpose)
    assert all(item["is_customized"] is False for item in body)


def test_update_and_reset_prompt_template(client):
    updated = client.patch(
        "/api/v1/prompt-templates/DAILY_FEEDBACK", json={"body": "カスタム文面"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["body"] == "カスタム文面"
    assert updated.json()["is_customized"] is True

    reset = client.post("/api/v1/prompt-templates/DAILY_FEEDBACK/reset")
    assert reset.status_code == 200
    assert reset.json()["is_customized"] is False
    assert reset.json()["body"] != "カスタム文面"


def test_update_prompt_template_rejects_empty_body(client):
    response = client.patch("/api/v1/prompt-templates/DAILY_FEEDBACK", json={"body": ""})
    assert response.status_code == 400


def test_prompt_template_unknown_purpose_returns_404(client):
    response = client.patch("/api/v1/prompt-templates/UNKNOWN", json={"body": "x"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
