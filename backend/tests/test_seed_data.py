"""完了条件: 起動時に初期データが投入され、再起動しても重複しないこと。"""

from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_DAILY_FEEDBACK_READING,
    AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_READING,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING,
    AI_ASSISTANT_UID_WEEKLY_SUMMARY_WORK,
    AI_WORK_RECENT_LOG_DAYS,
    SERVER_PORT,
)
from app.constants.enums import AiPurpose
from app.init.seed_data import (
    INITIAL_APP_SETTINGS,
    INITIAL_DAY_TYPE_DEFAULTS,
    INITIAL_PROMPT_TEMPLATES,
    backfill_reading_assistant_defaults,
    backfill_work_assistant_defaults,
    run_all,
)
from app.models.setting import AppSetting, DayTypeDefault, PromptTemplate


def test_run_all_seeds_all_expected_rows(db_session):
    run_all(db_session)

    assert db_session.query(AppSetting).count() == len(INITIAL_APP_SETTINGS)
    assert db_session.query(PromptTemplate).count() == len(INITIAL_PROMPT_TEMPLATES)
    assert db_session.query(DayTypeDefault).count() == len(INITIAL_DAY_TYPE_DEFAULTS)

    server_port = db_session.get(AppSetting, SERVER_PORT)
    assert server_port is not None
    assert server_port.value == "8100"


def test_run_all_is_idempotent_and_does_not_overwrite_customization(db_session):
    run_all(db_session)

    template = db_session.query(PromptTemplate).filter_by(purpose="DAILY_FEEDBACK").one()
    template.body = "利用者が編集したカスタム文面"
    template.is_customized = True
    db_session.commit()

    setting = db_session.get(AppSetting, SERVER_PORT)
    setting.value = "8200"
    db_session.commit()

    run_all(db_session)

    assert db_session.query(AppSetting).count() == len(INITIAL_APP_SETTINGS)
    assert db_session.query(PromptTemplate).count() == len(INITIAL_PROMPT_TEMPLATES)
    assert db_session.query(DayTypeDefault).count() == len(INITIAL_DAY_TYPE_DEFAULTS)

    reloaded_template = db_session.query(PromptTemplate).filter_by(purpose="DAILY_FEEDBACK").one()
    assert reloaded_template.body == "利用者が編集したカスタム文面"
    assert reloaded_template.is_customized is True

    reloaded_setting = db_session.get(AppSetting, SERVER_PORT)
    assert reloaded_setting.value == "8200"


def test_day_type_defaults_weekday_split(db_session):
    run_all(db_session)

    weekday_types = {row.weekday: row.day_type for row in db_session.query(DayTypeDefault).all()}
    for weekday in range(5):
        assert weekday_types[weekday].value == "PLAN"
    for weekday in (5, 6):
        assert weekday_types[weekday].value == "BUFFER"


def test_work_prompt_templates_and_settings_are_seeded(db_session):
    """完了条件: 仕事目標用のprompt_template・app_settingが初期投入されること
    （実装フェーズ分割計画書Phase20）。"""
    run_all(db_session)

    work_purposes = {
        AiPurpose.DAILY_FEEDBACK_WORK,
        AiPurpose.GOAL_RETROSPECTIVE_WORK_MONTHLY,
        AiPurpose.GOAL_RETROSPECTIVE_WORK_SEMIANNUAL,
    }
    for purpose in work_purposes:
        template = db_session.query(PromptTemplate).filter_by(purpose=purpose.value).one()
        assert template.body == INITIAL_PROMPT_TEMPLATES[purpose]
        assert template.is_customized is False

    work_recent_log_days = db_session.get(AppSetting, AI_WORK_RECENT_LOG_DAYS)
    assert work_recent_log_days is not None
    assert work_recent_log_days.value == "14"

    daily_feedback_assistant = db_session.get(AppSetting, AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK)
    assert daily_feedback_assistant is not None
    assert daily_feedback_assistant.value == "8ed280bb-3040-4ee3-9821-66bb7a4db125"

    # 月次報告・半期評価・仕事用週次要約は、総括レポート・読了レポートと同一アシスタント
    # （GPT-5.4・高性能）を既定値とする（2026-09-16、S-09・S-11解消）。
    for key in (
        AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY,
        AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL,
    ):
        setting = db_session.get(AppSetting, key)
        assert setting is not None
        assert setting.value == "d18ad1c0-c7e6-4651-9ff2-4fe86af1a73b"

    weekly_summary_work_assistant = db_session.get(AppSetting, AI_ASSISTANT_UID_WEEKLY_SUMMARY_WORK)
    assert weekly_summary_work_assistant is not None
    assert weekly_summary_work_assistant.value == "849c4042-c6de-404e-a1ce-89812eaf850e"


def test_backfill_reading_assistant_defaults_fills_existing_empty_value(db_session):
    """既にPhase16時点の空欄のままseed済みだった既存DBに対し、実環境での疎通確認後に
    選定した既定値（仕様書8.9.1・12章S-07解消）を一度きりで補うこと。"""
    run_all(db_session)
    setting = db_session.get(AppSetting, AI_ASSISTANT_UID_DAILY_FEEDBACK_READING)
    setting.value = ""
    db_session.commit()

    backfill_reading_assistant_defaults(db_session)
    db_session.commit()

    reloaded = db_session.get(AppSetting, AI_ASSISTANT_UID_DAILY_FEEDBACK_READING)
    assert reloaded.value == INITIAL_APP_SETTINGS[AI_ASSISTANT_UID_DAILY_FEEDBACK_READING][0]


def test_backfill_reading_assistant_defaults_does_not_overwrite_customization(db_session):
    run_all(db_session)
    setting = db_session.get(AppSetting, AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_READING)
    setting.value = "利用者が選択済みのUID"
    db_session.commit()

    backfill_reading_assistant_defaults(db_session)
    db_session.commit()

    reloaded = db_session.get(AppSetting, AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_READING)
    assert reloaded.value == "利用者が選択済みのUID"


def test_backfill_reading_assistant_defaults_fills_weekly_summary(db_session):
    """L-11で新設した読書用週次要約も、既存の空欄DBに対して一度きりで補われること
    （2026-09-16、S-11解消）。"""
    run_all(db_session)
    setting = db_session.get(AppSetting, AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING)
    setting.value = ""
    db_session.commit()

    backfill_reading_assistant_defaults(db_session)
    db_session.commit()

    reloaded = db_session.get(AppSetting, AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING)
    assert reloaded.value == INITIAL_APP_SETTINGS[AI_ASSISTANT_UID_WEEKLY_SUMMARY_READING][0]


def test_backfill_work_assistant_defaults_fills_existing_empty_value(db_session):
    """既に空欄のままseed済みだった既存DBに対し、実環境での疎通確認後に選定した
    仕事の日次フィードバック用既定値を一度きりで補うこと（実装フェーズ分割計画書Phase22）。"""
    run_all(db_session)
    setting = db_session.get(AppSetting, AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK)
    setting.value = ""
    db_session.commit()

    backfill_work_assistant_defaults(db_session)
    db_session.commit()

    reloaded = db_session.get(AppSetting, AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK)
    assert reloaded.value == INITIAL_APP_SETTINGS[AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK][0]


def test_backfill_work_assistant_defaults_does_not_overwrite_customization(db_session):
    run_all(db_session)
    setting = db_session.get(AppSetting, AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK)
    setting.value = "利用者が選択済みのUID"
    db_session.commit()

    backfill_work_assistant_defaults(db_session)
    db_session.commit()

    reloaded = db_session.get(AppSetting, AI_ASSISTANT_UID_DAILY_FEEDBACK_WORK)
    assert reloaded.value == "利用者が選択済みのUID"


def test_backfill_work_assistant_defaults_fills_monthly_semiannual_and_weekly_summary(db_session):
    """月次報告・半期評価（S-09）・仕事用週次要約（L-11、S-11）も、既存の空欄DBに対して
    一度きりで補われること（2026-09-16解消）。"""
    run_all(db_session)
    keys = (
        AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY,
        AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL,
        AI_ASSISTANT_UID_WEEKLY_SUMMARY_WORK,
    )
    for key in keys:
        db_session.get(AppSetting, key).value = ""
    db_session.commit()

    backfill_work_assistant_defaults(db_session)
    db_session.commit()

    for key in keys:
        reloaded = db_session.get(AppSetting, key)
        assert reloaded.value == INITIAL_APP_SETTINGS[key][0]


def test_backfill_work_assistant_defaults_does_not_overwrite_semiannual_customization(db_session):
    run_all(db_session)
    setting = db_session.get(AppSetting, AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL)
    setting.value = "利用者が選択済みのUID"
    db_session.commit()

    backfill_work_assistant_defaults(db_session)
    db_session.commit()

    reloaded = db_session.get(AppSetting, AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL)
    assert reloaded.value == "利用者が選択済みのUID"
