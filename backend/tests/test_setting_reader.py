"""setting_reader のテスト（型付き読み出しとキー不在時の例外）。"""

import pytest

from app.constants.app_setting_keys import (
    CALENDAR_DAY_BOUNDARY_HOUR,
    HOLIDAY_TREAT_AS_BUFFER,
    THRESHOLD_REPLAN_OVERRUN_DAYS,
    THRESHOLD_WARNING_RATIO,
)
from app.models.setting import AppSetting
from app.services import setting_reader
from app.services.exceptions import AppSettingNotFoundError


def test_get_str_returns_raw_value(seeded_session):
    assert setting_reader.get_str(seeded_session, "display.locale") == "ja"


def test_get_int_converts_value(seeded_session):
    assert setting_reader.get_int(seeded_session, THRESHOLD_REPLAN_OVERRUN_DAYS) == 3
    assert setting_reader.get_int(seeded_session, CALENDAR_DAY_BOUNDARY_HOUR) == 0


def test_get_float_converts_value(seeded_session):
    assert setting_reader.get_float(seeded_session, THRESHOLD_WARNING_RATIO) == 1.20


def test_get_bool_returns_true_for_true_value(seeded_session):
    assert setting_reader.get_bool(seeded_session, HOLIDAY_TREAT_AS_BUFFER) is True


def test_get_bool_returns_false_for_non_true_value(seeded_session):
    row = seeded_session.get(AppSetting, HOLIDAY_TREAT_AS_BUFFER)
    row.value = "false"
    seeded_session.flush()

    assert setting_reader.get_bool(seeded_session, HOLIDAY_TREAT_AS_BUFFER) is False


def test_get_raises_when_key_missing(db_session):
    """境界値: 未投入のキーを参照した場合にドメイン例外が発生すること。"""
    with pytest.raises(AppSettingNotFoundError) as excinfo:
        setting_reader.get_str(db_session, "does.not.exist")

    assert excinfo.value.key == "does.not.exist"
