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
    変更可能であり、実環境での疎通確認済みの既定値が入っていること
    （仕様書6.11「全ての設定項目を画面上から変更可能」、8.9.1、12章S-07解消）。"""
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    body = response.json()
    assert (
        body["ai_connection"]["assistant_uid_daily_feedback_reading"]
        == "8ed280bb-3040-4ee3-9821-66bb7a4db125"
    )
    assert (
        body["ai_connection"]["assistant_uid_goal_retrospective_reading"]
        == "d18ad1c0-c7e6-4651-9ff2-4fe86af1a73b"
    )
    assert (
        body["ai_connection"]["assistant_uid_weekly_summary_reading"]
        == "849c4042-c6de-404e-a1ce-89812eaf850e"
    )
    assert body["prompt_degradation"]["reading_recall_recent_days"] == 14


def test_patch_settings_updates_reading_assistant_uids_and_recall_window(client):
    response = client.patch(
        "/api/v1/settings",
        json={
            "ai_connection": {
                "assistant_uid_daily_feedback_reading": "uid-daily-reading",
                "assistant_uid_goal_retrospective_reading": "uid-retrospective-reading",
                "assistant_uid_weekly_summary_reading": "uid-weekly-summary-reading",
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
    assert (
        body["ai_connection"]["assistant_uid_weekly_summary_reading"]
        == "uid-weekly-summary-reading"
    )
    assert body["prompt_degradation"]["reading_recall_recent_days"] == 7


def test_get_settings_includes_work_assistant_uids(client):
    """仕事用のアシスタント設定が設定画面（GET /settings）から参照可能であり、
    実環境での疎通確認済みの既定値が入っていること（L-09解消。今回のセッションで
    読書と同様に設定APIへ露出した、仕様書6.11「全ての設定項目を画面上から変更可能」）。"""
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    body = response.json()
    assert (
        body["ai_connection"]["assistant_uid_daily_feedback_work"]
        == "8ed280bb-3040-4ee3-9821-66bb7a4db125"
    )
    assert (
        body["ai_connection"]["assistant_uid_goal_retrospective_work_monthly"]
        == "d18ad1c0-c7e6-4651-9ff2-4fe86af1a73b"
    )
    assert (
        body["ai_connection"]["assistant_uid_goal_retrospective_work_semiannual"]
        == "d18ad1c0-c7e6-4651-9ff2-4fe86af1a73b"
    )
    assert (
        body["ai_connection"]["assistant_uid_weekly_summary_work"]
        == "849c4042-c6de-404e-a1ce-89812eaf850e"
    )


def test_patch_settings_updates_work_assistant_uids(client):
    response = client.patch(
        "/api/v1/settings",
        json={
            "ai_connection": {
                "assistant_uid_daily_feedback_work": "uid-daily-work",
                "assistant_uid_goal_retrospective_work_monthly": "uid-monthly-work",
                "assistant_uid_goal_retrospective_work_semiannual": "uid-semiannual-work",
                "assistant_uid_weekly_summary_work": "uid-weekly-summary-work",
            }
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ai_connection"]["assistant_uid_daily_feedback_work"] == "uid-daily-work"
    assert (
        body["ai_connection"]["assistant_uid_goal_retrospective_work_monthly"] == "uid-monthly-work"
    )
    assert (
        body["ai_connection"]["assistant_uid_goal_retrospective_work_semiannual"]
        == "uid-semiannual-work"
    )
    assert body["ai_connection"]["assistant_uid_weekly_summary_work"] == "uid-weekly-summary-work"

    confirmed = client.get("/api/v1/settings").json()
    assert confirmed["ai_connection"]["assistant_uid_daily_feedback_work"] == "uid-daily-work"


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
    updated = client.patch("/api/v1/prompt-templates/DAILY_FEEDBACK", json={"body": "カスタム文面"})
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


class TestDesktopSettingsApi:
    """デスクトップ常駐・記録リマインドの設定（SC-11、Phase37）。"""

    def test_get_returns_the_desktop_group(self, client):
        body = client.get("/api/v1/settings").json()

        assert body["desktop"] == {
            "open_browser_on_startup": True,
            "launch_at_login": False,
            "notification_enabled": True,
            "notification_time": "21:00",
        }

    def test_patch_updates_the_desktop_group(self, client):
        response = client.patch(
            "/api/v1/settings",
            json={"desktop": {"launch_at_login": True, "notification_time": "07:30"}},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["desktop"]["launch_at_login"] is True
        assert body["desktop"]["notification_time"] == "07:30"
        # 指定していない項目は元のまま。
        assert body["desktop"]["notification_enabled"] is True

    def test_patch_rejects_a_malformed_notification_time(self, client):
        """サービス層のドメイン例外がAPI層でエラーコードへ変換されること（技術選定書7.3）。"""
        response = client.patch(
            "/api/v1/settings", json={"desktop": {"notification_time": "25:00"}}
        )

        assert response.status_code == 400, response.text
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_patch_rejects_an_empty_notification_time(self, client):
        """スキーマ側（min_length）で弾かれる場合も同じエラーコードになること。"""
        response = client.patch("/api/v1/settings", json={"desktop": {"notification_time": ""}})

        assert response.status_code == 400, response.text
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_patch_keeps_the_stored_value_when_rejected(self, client):
        client.patch("/api/v1/settings", json={"desktop": {"notification_time": "25:00"}})

        body = client.get("/api/v1/settings").json()
        assert body["desktop"]["notification_time"] == "21:00"
