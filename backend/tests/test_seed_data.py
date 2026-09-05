"""完了条件: 起動時に初期データが投入され、再起動しても重複しないこと。"""

from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_DAILY_FEEDBACK_READING,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_READING,
    AI_WORK_RECENT_LOG_DAYS,
    SERVER_PORT,
)
from app.constants.enums import AiPurpose
from app.init.seed_data import (
    INITIAL_APP_SETTINGS,
    INITIAL_DAY_TYPE_DEFAULTS,
    INITIAL_PROMPT_TEMPLATES,
    backfill_reading_assistant_defaults,
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
        template = (
            db_session.query(PromptTemplate).filter_by(purpose=purpose.value).one()
        )
        assert template.body == INITIAL_PROMPT_TEMPLATES[purpose]
        assert template.is_customized is False

    work_recent_log_days = db_session.get(AppSetting, AI_WORK_RECENT_LOG_DAYS)
    assert work_recent_log_days is not None
    assert work_recent_log_days.value == "14"


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
