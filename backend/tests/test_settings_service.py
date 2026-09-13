"""settings_service のテスト（仕様書6.11、実装フェーズ分割計画書Phase7）。"""

import pytest

from app.constants.app_setting_keys import AI_HOST
from app.constants.enums import AiPurpose
from app.models.setting import AppSetting, PromptTemplate
from app.services import settings_service
from app.services.exceptions import AppSettingNotFoundError, NotFoundError, ValidationError


def test_get_app_settings_returns_seeded_defaults(seeded_session):
    settings = settings_service.get_app_settings(seeded_session)
    assert settings.ai_connection.folder_prefix == "ミチナリ"
    assert settings.ai_connection.timeout_seconds == 60
    assert settings.threshold.warning_ratio == 1.20
    assert settings.threshold.replan_overrun_days == 3
    assert settings.prompt_degradation.max_prompt_chars == 30000
    assert settings.display.locale == "ja"
    assert settings.display.theme == "system"
    assert settings.display.default_granularity == "WEEK"
    assert settings.log.ai_enabled is True
    assert settings.log.retention_days == 90


def test_update_app_settings_partial_update_keeps_other_fields(seeded_session):
    updated = settings_service.update_app_settings(
        seeded_session,
        ai_connection={"folder_prefix": "資格試験"},
        threshold={"warning_ratio": 1.5},
    )
    assert updated.ai_connection.folder_prefix == "資格試験"
    assert updated.ai_connection.timeout_seconds == 60
    assert updated.threshold.warning_ratio == 1.5
    assert updated.threshold.replan_overrun_days == 3


def test_update_app_settings_rejects_invalid_theme(seeded_session):
    with pytest.raises(ValidationError):
        settings_service.update_app_settings(seeded_session, display={"theme": "rainbow"})


def test_update_app_settings_rejects_invalid_granularity(seeded_session):
    with pytest.raises(ValidationError):
        settings_service.update_app_settings(
            seeded_session, display={"default_granularity": "YEAR"}
        )


def test_update_app_settings_rejects_invalid_locale(seeded_session):
    with pytest.raises(ValidationError):
        settings_service.update_app_settings(seeded_session, display={"locale": "en"})


def test_update_app_settings_log_and_prompt_degradation(seeded_session):
    updated = settings_service.update_app_settings(
        seeded_session,
        log={"ai_enabled": False, "retention_days": 30},
        prompt_degradation={"max_prompt_chars": 20000, "summary_inject_weeks": 2},
    )
    assert updated.log.ai_enabled is False
    assert updated.log.retention_days == 30
    assert updated.prompt_degradation.max_prompt_chars == 20000
    assert updated.prompt_degradation.summary_inject_weeks == 2


def test_update_app_settings_accepts_each_field_independently(seeded_session):
    """各グループの2フィールド目のみを指定した場合でも、1フィールド目は変更されない。"""
    updated = settings_service.update_app_settings(
        seeded_session,
        threshold={"replan_overrun_days": 5},
        prompt_degradation={"summary_inject_weeks": 6},
        log={"retention_days": 45},
    )
    assert updated.threshold.warning_ratio == 1.20
    assert updated.threshold.replan_overrun_days == 5
    assert updated.prompt_degradation.max_prompt_chars == 30000
    assert updated.prompt_degradation.summary_inject_weeks == 6
    assert updated.log.ai_enabled is True
    assert updated.log.retention_days == 45


def test_update_app_settings_updates_display_theme_and_granularity(seeded_session):
    updated = settings_service.update_app_settings(
        seeded_session, display={"locale": "ja", "theme": "dark", "default_granularity": "MONTH"}
    )
    assert updated.display.locale == "ja"
    assert updated.display.theme == "dark"
    assert updated.display.default_granularity == "MONTH"


def test_update_app_settings_ignores_explicit_none_field(seeded_session):
    """明示的にnullが送られたフィールドは変更しない（他フィールドと同時指定時の分岐）。"""
    updated = settings_service.update_app_settings(
        seeded_session, ai_connection={"host": None, "folder_prefix": "資格試験"}
    )
    assert updated.ai_connection.host == ""
    assert updated.ai_connection.folder_prefix == "資格試験"


def test_update_app_settings_accepts_only_first_field_of_each_group(seeded_session):
    """各グループの1フィールド目のみを指定した場合、2フィールド目の分岐を通らずに終了する。"""
    updated = settings_service.update_app_settings(
        seeded_session,
        prompt_degradation={"max_prompt_chars": 25000},
        display={"theme": "light"},
        log={"ai_enabled": False},
    )
    assert updated.prompt_degradation.max_prompt_chars == 25000
    assert updated.prompt_degradation.summary_inject_weeks == 4
    assert updated.display.theme == "light"
    assert updated.display.default_granularity == "WEEK"
    assert updated.log.ai_enabled is False
    assert updated.log.retention_days == 90


def test_update_app_settings_missing_row_raises_app_setting_not_found(seeded_session):
    seeded_session.query(AppSetting).filter(AppSetting.key == AI_HOST).delete()
    seeded_session.flush()
    with pytest.raises(AppSettingNotFoundError):
        settings_service.update_app_settings(seeded_session, ai_connection={"host": "example.com"})


def test_get_prompt_template_missing_row_raises_not_found(seeded_session):
    seeded_session.query(PromptTemplate).filter(
        PromptTemplate.purpose == AiPurpose.DAILY_FEEDBACK.value
    ).delete()
    seeded_session.flush()
    with pytest.raises(NotFoundError):
        settings_service.get_prompt_template(seeded_session, AiPurpose.DAILY_FEEDBACK)


def test_list_prompt_templates_returns_all_purposes(seeded_session):
    templates = settings_service.list_prompt_templates(seeded_session)
    purposes = {t.purpose for t in templates}
    assert purposes == {p.value for p in AiPurpose}
    assert all(t.is_customized is False for t in templates)


def test_update_prompt_template_marks_customized(seeded_session):
    updated = settings_service.update_prompt_template(
        seeded_session, AiPurpose.DAILY_FEEDBACK, "カスタム文面"
    )
    assert updated.body == "カスタム文面"
    assert updated.is_customized is True


def test_reset_prompt_template_restores_initial_body(seeded_session):
    settings_service.update_prompt_template(
        seeded_session, AiPurpose.DAILY_FEEDBACK, "カスタム文面"
    )
    reset = settings_service.reset_prompt_template(seeded_session, AiPurpose.DAILY_FEEDBACK)
    assert reset.is_customized is False
    assert reset.body == settings_service.INITIAL_PROMPT_TEMPLATES[AiPurpose.DAILY_FEEDBACK]


class TestDesktopSettings:
    """デスクトップ常駐・記録リマインドの設定（実装スコープA〜C、Phase37）。"""

    def test_get_returns_seeded_defaults(self, seeded_session):
        """既定値が仕様どおりであること（ブラウザは毎回開く・自動起動は無効・通知は21:00）。"""
        desktop = settings_service.get_app_settings(seeded_session).desktop

        assert desktop.open_browser_on_startup is True
        assert desktop.launch_at_login is False
        assert desktop.notification_enabled is True
        assert desktop.notification_time == "21:00"

    def test_update_writes_every_field(self, seeded_session):
        updated = settings_service.update_app_settings(
            seeded_session,
            desktop={
                "open_browser_on_startup": False,
                "launch_at_login": True,
                "notification_enabled": False,
                "notification_time": "07:30",
            },
        )

        assert updated.desktop.open_browser_on_startup is False
        assert updated.desktop.launch_at_login is True
        assert updated.desktop.notification_enabled is False
        assert updated.desktop.notification_time == "07:30"

    def test_update_keeps_untouched_fields(self, seeded_session):
        updated = settings_service.update_app_settings(
            seeded_session, desktop={"launch_at_login": True}
        )

        assert updated.desktop.launch_at_login is True
        assert updated.desktop.open_browser_on_startup is True
        assert updated.desktop.notification_time == "21:00"

    def test_update_keeps_other_groups(self, seeded_session):
        updated = settings_service.update_app_settings(
            seeded_session, desktop={"notification_enabled": False}
        )

        assert updated.display.theme == "system"
        assert updated.log.ai_enabled is True

    @pytest.mark.parametrize("value", ["24:00", "9:00", "夜9時", ""])
    def test_update_rejects_a_malformed_notification_time(self, seeded_session, value: str):
        """判定に使う形式（notification_service）と同じ規則で弾くこと。"""
        with pytest.raises(ValidationError):
            settings_service.update_app_settings(
                seeded_session, desktop={"notification_time": value}
            )

    def test_update_does_not_store_a_rejected_notification_time(self, seeded_session):
        with pytest.raises(ValidationError):
            settings_service.update_app_settings(
                seeded_session, desktop={"notification_time": "25:00"}
            )

        assert (
            settings_service.get_app_settings(seeded_session).desktop.notification_time == "21:00"
        )
