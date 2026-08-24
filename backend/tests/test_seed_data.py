"""完了条件: 起動時に初期データが投入され、再起動しても重複しないこと。"""

from app.constants.app_setting_keys import SERVER_PORT
from app.init.seed_data import (
    INITIAL_APP_SETTINGS,
    INITIAL_DAY_TYPE_DEFAULTS,
    INITIAL_PROMPT_TEMPLATES,
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
