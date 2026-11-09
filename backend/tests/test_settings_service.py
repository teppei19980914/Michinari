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
    # 添付ファイル機能導入にあわせ既定値を50000へ引き上げ（開発Todo_添付ファイル機能_v1.0 A5）。
    assert settings.prompt_degradation.max_prompt_chars == 50000
    assert settings.display.locale == "ja"
    assert settings.display.theme == "system"
    assert settings.display.default_granularity == "WEEK"
    assert settings.display.accent_color == "blue"
    assert settings.display.font_scale == "standard"
    assert settings.log.ai_enabled is True
    assert settings.log.retention_days == 90
    assert settings.milestone_threshold.consecutive_days_thresholds == "3,7,14,30,50,100,200,365"
    assert settings.milestone_threshold.work_record_count_thresholds == "10,50,100"


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
        settings_service.update_app_settings(seeded_session, display={"locale": "fr"})


def test_update_app_settings_accepts_english_locale(seeded_session):
    updated = settings_service.update_app_settings(seeded_session, display={"locale": "en"})
    assert updated.display.locale == "en"


def test_update_app_settings_rejects_invalid_accent_color(seeded_session):
    with pytest.raises(ValidationError):
        settings_service.update_app_settings(seeded_session, display={"accent_color": "rainbow"})


def test_update_app_settings_rejects_invalid_font_scale(seeded_session):
    with pytest.raises(ValidationError):
        settings_service.update_app_settings(seeded_session, display={"font_scale": "huge"})


def test_update_app_settings_log_and_prompt_degradation(seeded_session):
    updated = settings_service.update_app_settings(
        seeded_session,
        log={"ai_enabled": False, "retention_days": 30},
        prompt_degradation={"max_prompt_chars": 20000, "perspective_suggestion_min_records": 2},
    )
    assert updated.log.ai_enabled is False
    assert updated.log.retention_days == 30
    assert updated.prompt_degradation.max_prompt_chars == 20000
    assert updated.prompt_degradation.perspective_suggestion_min_records == 2


def test_update_app_settings_accepts_each_field_independently(seeded_session):
    """各グループの2フィールド目のみを指定した場合でも、1フィールド目は変更されない。"""
    updated = settings_service.update_app_settings(
        seeded_session,
        threshold={"replan_overrun_days": 5},
        prompt_degradation={"perspective_suggestion_min_records": 6},
        log={"retention_days": 45},
    )
    assert updated.threshold.warning_ratio == 1.20
    assert updated.threshold.replan_overrun_days == 5
    assert updated.prompt_degradation.max_prompt_chars == 50000
    assert updated.prompt_degradation.perspective_suggestion_min_records == 6
    assert updated.log.ai_enabled is True
    assert updated.log.retention_days == 45


def test_update_app_settings_updates_display_theme_and_granularity(seeded_session):
    updated = settings_service.update_app_settings(
        seeded_session,
        display={
            "locale": "ja",
            "theme": "dark",
            "default_granularity": "MONTH",
            "accent_color": "green",
            "font_scale": "large",
        },
    )
    assert updated.display.locale == "ja"
    assert updated.display.theme == "dark"
    assert updated.display.default_granularity == "MONTH"
    assert updated.display.accent_color == "green"
    assert updated.display.font_scale == "large"


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
    assert updated.prompt_degradation.perspective_suggestion_min_records == 3
    assert updated.display.theme == "light"
    assert updated.display.default_granularity == "WEEK"
    assert updated.display.accent_color == "blue"
    assert updated.display.font_scale == "standard"
    assert updated.log.ai_enabled is False
    assert updated.log.retention_days == 90


def test_update_app_settings_missing_row_raises_app_setting_not_found(seeded_session):
    seeded_session.query(AppSetting).filter(AppSetting.key == AI_HOST).delete()
    seeded_session.flush()
    with pytest.raises(AppSettingNotFoundError):
        settings_service.update_app_settings(seeded_session, ai_connection={"host": "example.com"})


def test_update_app_settings_normalizes_milestone_thresholds(seeded_session):
    """重複・順序違い・空白混入を正規化（昇順・重複除去）する（開発Todo_節目のお祝い_v1.0 M3）。"""
    updated = settings_service.update_app_settings(
        seeded_session, milestone_threshold={"consecutive_days_thresholds": " 7, 3,3 ,14"}
    )
    assert updated.milestone_threshold.consecutive_days_thresholds == "3,7,14"


def test_update_app_settings_rejects_non_integer_milestone_threshold(seeded_session):
    with pytest.raises(ValidationError):
        settings_service.update_app_settings(
            seeded_session, milestone_threshold={"consecutive_days_thresholds": "3,abc"}
        )


def test_update_app_settings_rejects_empty_milestone_threshold_item(seeded_session):
    with pytest.raises(ValidationError):
        settings_service.update_app_settings(
            seeded_session, milestone_threshold={"consecutive_days_thresholds": "3,,7"}
        )


def test_update_app_settings_rejects_non_positive_milestone_threshold(seeded_session):
    with pytest.raises(ValidationError):
        settings_service.update_app_settings(
            seeded_session, milestone_threshold={"consecutive_days_thresholds": "0,3"}
        )


def test_update_app_settings_accepts_each_milestone_threshold_field_independently(seeded_session):
    updated = settings_service.update_app_settings(
        seeded_session,
        milestone_threshold={
            "total_record_days_thresholds": "1,2",
            "reading_total_pages_thresholds": "10,20",
            "reading_completed_books_thresholds": "1",
            "exam_overall_progress_thresholds": "50",
            "work_record_count_thresholds": "5",
        },
    )
    assert updated.milestone_threshold.total_record_days_thresholds == "1,2"
    assert updated.milestone_threshold.reading_total_pages_thresholds == "10,20"
    assert updated.milestone_threshold.reading_completed_books_thresholds == "1"
    assert updated.milestone_threshold.exam_overall_progress_thresholds == "50"
    assert updated.milestone_threshold.work_record_count_thresholds == "5"
    # 更新していないフィールドは既定値のまま。
    assert updated.milestone_threshold.consecutive_days_thresholds == "3,7,14,30,50,100,200,365"


def test_get_app_settings_returns_on_this_day_defaults(seeded_session):
    """開発Todo_1年前の今日_v1.0 §0 V1〜V3、V12。"""
    settings = settings_service.get_app_settings(seeded_session)
    assert settings.on_this_day.enabled is True
    assert settings.on_this_day.candidate_months_ago == "1,6,12"
    assert settings.on_this_day.show_probability == 0.3
    assert settings.on_this_day.body_preview_chars == 100


def test_update_app_settings_updates_on_this_day_fields_independently(seeded_session):
    updated = settings_service.update_app_settings(
        seeded_session,
        on_this_day={"enabled": False, "show_probability": 0.5, "body_preview_chars": 50},
    )
    assert updated.on_this_day.enabled is False
    assert updated.on_this_day.show_probability == 0.5
    assert updated.on_this_day.body_preview_chars == 50
    # 更新していないフィールドは既定値のまま。
    assert updated.on_this_day.candidate_months_ago == "1,6,12"


def test_update_app_settings_normalizes_on_this_day_candidate_months_ago(seeded_session):
    updated = settings_service.update_app_settings(
        seeded_session, on_this_day={"candidate_months_ago": " 12, 1,1 ,6"}
    )
    assert updated.on_this_day.candidate_months_ago == "1,6,12"


def test_update_app_settings_rejects_non_integer_on_this_day_candidate(seeded_session):
    with pytest.raises(ValidationError):
        settings_service.update_app_settings(
            seeded_session, on_this_day={"candidate_months_ago": "1,abc"}
        )


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

    def test_get_returns_reminder_onboarding_flags_seeded_defaults(self, seeded_session):
        """新規インストール相当（目標0件）の既定値は両方false（開発Todo リマインド導線 D3・D5）。"""
        desktop = settings_service.get_app_settings(seeded_session).desktop

        assert desktop.reminder_onboarding_shown is False
        assert desktop.autostart_banner_dismissed is False

    def test_update_writes_reminder_onboarding_flags(self, seeded_session):
        updated = settings_service.update_app_settings(
            seeded_session,
            desktop={"reminder_onboarding_shown": True, "autostart_banner_dismissed": True},
        )

        assert updated.desktop.reminder_onboarding_shown is True
        assert updated.desktop.autostart_banner_dismissed is True


class TestResolveReminderOnboardingFlags:
    """`GET /dashboard`が表示する2つの案内の表示条件（開発Todo リマインド導線 D2・D5）。"""

    def test_shows_onboarding_prompt_until_marked_shown(self, seeded_session):
        flags = settings_service.resolve_reminder_onboarding_flags(seeded_session)
        assert flags.show_reminder_onboarding_prompt is True

        settings_service.update_app_settings(
            seeded_session, desktop={"reminder_onboarding_shown": True}
        )

        flags = settings_service.resolve_reminder_onboarding_flags(seeded_session)
        assert flags.show_reminder_onboarding_prompt is False

    def test_shows_autostart_banner_only_when_notification_on_and_autostart_off_and_not_dismissed(
        self, seeded_session
    ):
        # 既定値（通知オン・自動起動オフ・未クローズ）では出る。
        flags = settings_service.resolve_reminder_onboarding_flags(seeded_session)
        assert flags.show_reminder_autostart_banner is True

        # 自動起動をオンにすると出なくなる。
        settings_service.update_app_settings(seeded_session, desktop={"launch_at_login": True})
        assert (
            settings_service.resolve_reminder_onboarding_flags(
                seeded_session
            ).show_reminder_autostart_banner
            is False
        )

        # 自動起動をオフへ戻しても、通知自体がオフなら出ない。
        settings_service.update_app_settings(
            seeded_session, desktop={"launch_at_login": False, "notification_enabled": False}
        )
        assert (
            settings_service.resolve_reminder_onboarding_flags(
                seeded_session
            ).show_reminder_autostart_banner
            is False
        )

        # 通知を戻しても、閉じた（dismissed）後は出ない。
        settings_service.update_app_settings(
            seeded_session,
            desktop={"notification_enabled": True, "autostart_banner_dismissed": True},
        )
        assert (
            settings_service.resolve_reminder_onboarding_flags(
                seeded_session
            ).show_reminder_autostart_banner
            is False
        )
