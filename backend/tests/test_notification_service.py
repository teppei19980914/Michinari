"""notification_service のテスト（記録リマインドの判定、Phase37）。

実装スコープCが定める通知条件を表として網羅する。

| 条件 | 期待 |
| --- | --- |
| 通知が無効 | 通知しない |
| 除外日（OFF） | 通知しない |
| 記録済み（進捗のみ登録済み／報告済み） | 通知しない |
| 予備日（BUFFER） | 通知する（文面が異なる） |
| 計画日（PLAN）で未記録 | 通知する |

論理的な本日を使っていること（システム日付を直接見ていないこと）も検証する。境界時刻を
0時以外にした利用者に対して、深夜だけ画面と食い違う判定になるのを防ぐためである。
"""

import datetime as dt

import pytest

from app.constants import locale_keys
from app.constants.app_setting_keys import (
    CALENDAR_DAY_BOUNDARY_HOUR,
    DESKTOP_NOTIFICATION_ENABLED,
    DESKTOP_NOTIFICATION_TIME,
)
from app.constants.enums import DayType, RecordState
from app.models.setting import AppSetting, CalendarDayOverride
from app.services import calendar_service, notification_service, record_service
from app.services.exceptions import ValidationError


def _set_setting(session, key: str, value: str) -> None:
    session.get(AppSetting, key).value = value
    session.flush()


def _override_day_type(session, target_date: dt.date, day_type: DayType) -> None:
    calendar_service.set_day_type_override(session, target_date, day_type, note=None)
    session.flush()


class TestParseNotificationTime:
    def test_parses_valid_time(self):
        assert notification_service.parse_notification_time("21:00") == dt.time(21, 0)

    def test_accepts_surrounding_whitespace(self):
        assert notification_service.parse_notification_time(" 07:05 ") == dt.time(7, 5)

    def test_accepts_boundary_values(self):
        assert notification_service.parse_notification_time("00:00") == dt.time(0, 0)
        assert notification_service.parse_notification_time("23:59") == dt.time(23, 59)

    @pytest.mark.parametrize("value", ["24:00", "21:60", "9:00", "2100", "", "夜9時"])
    def test_rejects_invalid_format(self, value: str):
        with pytest.raises(ValidationError):
            notification_service.parse_notification_time(value)


class TestHasCrossedNotificationTime:
    """通知時刻を「またいだ瞬間だけ」1回判定されること。"""

    def test_true_when_the_interval_spans_the_time(self):
        assert notification_service.has_crossed_notification_time(
            dt.time(21, 0),
            dt.datetime(2026, 9, 13, 20, 59, 30),
            dt.datetime(2026, 9, 13, 21, 0, 30),
        )

    def test_false_before_the_time(self):
        assert not notification_service.has_crossed_notification_time(
            dt.time(21, 0),
            dt.datetime(2026, 9, 13, 20, 57),
            dt.datetime(2026, 9, 13, 20, 58),
        )

    def test_false_after_the_time_has_already_passed(self):
        """起動時に当日の通知時刻を過ぎていても蒸し返さないこと（呼び出し側が起動時刻を渡す）。"""
        assert not notification_service.has_crossed_notification_time(
            dt.time(21, 0),
            dt.datetime(2026, 9, 13, 22, 0),
            dt.datetime(2026, 9, 13, 22, 1),
        )

    def test_true_when_the_boundary_is_hit_exactly(self):
        assert notification_service.has_crossed_notification_time(
            dt.time(21, 0),
            dt.datetime(2026, 9, 13, 20, 59),
            dt.datetime(2026, 9, 13, 21, 0),
        )

    def test_true_when_the_interval_spans_midnight_and_the_next_day(self):
        """スリープからの長時間復帰でも、間に挟まった通知時刻を取りこぼさないこと。"""
        assert notification_service.has_crossed_notification_time(
            dt.time(21, 0),
            dt.datetime(2026, 9, 13, 20, 0),
            dt.datetime(2026, 9, 15, 12, 0),
        )

    def test_false_when_the_clock_goes_backwards(self):
        """時計の手動調整で時刻が巻き戻った場合は判定しないこと。"""
        assert not notification_service.has_crossed_notification_time(
            dt.time(21, 0),
            dt.datetime(2026, 9, 13, 22, 0),
            dt.datetime(2026, 9, 13, 20, 0),
        )


class TestReadNotificationTime:
    def test_reads_the_configured_value(self, seeded_session):
        _set_setting(seeded_session, DESKTOP_NOTIFICATION_TIME, "07:30")
        assert notification_service.read_notification_time(seeded_session) == dt.time(7, 30)

    def test_raises_when_the_stored_value_is_broken(self, seeded_session):
        _set_setting(seeded_session, DESKTOP_NOTIFICATION_TIME, "とても遅い時間")
        with pytest.raises(ValidationError):
            notification_service.read_notification_time(seeded_session)


class TestEvaluate:
    def test_notifies_on_a_plan_day_without_any_record(self, seeded_session):
        # 曜日既定値では土日がBUFFERになるため、実行日に左右されないよう明示的に計画日にする。
        today = notification_service.goal_service.resolve_today(seeded_session)
        _override_day_type(seeded_session, today, DayType.PLAN)

        decision = notification_service.evaluate(seeded_session)

        assert decision.should_notify
        assert decision.title_key == locale_keys.NOTIFICATION_PLAN_TITLE
        assert decision.body_key == locale_keys.NOTIFICATION_PLAN_BODY
        assert decision.skip_reason is None

    def test_uses_the_buffer_wording_on_a_buffer_day(self, seeded_session):
        today = notification_service.goal_service.resolve_today(seeded_session)
        _override_day_type(seeded_session, today, DayType.BUFFER)

        decision = notification_service.evaluate(seeded_session)

        assert decision.should_notify
        assert decision.title_key == locale_keys.NOTIFICATION_BUFFER_TITLE
        assert decision.body_key == locale_keys.NOTIFICATION_BUFFER_BODY

    def test_does_not_notify_on_an_excluded_day(self, seeded_session):
        today = notification_service.goal_service.resolve_today(seeded_session)
        _override_day_type(seeded_session, today, DayType.OFF)

        decision = notification_service.evaluate(seeded_session)

        assert not decision.should_notify
        assert decision.skip_reason == "day_type_off"

    def test_does_not_notify_when_notifications_are_disabled(self, seeded_session):
        _set_setting(seeded_session, DESKTOP_NOTIFICATION_ENABLED, "false")

        decision = notification_service.evaluate(seeded_session)

        assert not decision.should_notify
        assert decision.skip_reason == "disabled"

    @pytest.mark.parametrize(
        "state",
        [RecordState.PROGRESS_ONLY, RecordState.REPORTED],
        ids=["progress_only", "reported"],
    )
    @pytest.mark.parametrize(
        "column",
        ["exam_record_state", "reading_record_state", "work_record_state"],
        ids=["exam", "reading", "work"],
    )
    def test_does_not_notify_when_the_day_is_already_recorded(
        self, seeded_session, column: str, state
    ):
        """**どのカテゴリで記録しても**「記録済み」と見なすこと。

        資格試験だけを見る実装に退化すると、読書・仕事だけを記録している利用者へ
        「記録したのに通知が来る」ことになる。
        """
        today = notification_service.goal_service.resolve_today(seeded_session)
        record = record_service.ensure_daily_record(seeded_session, today)
        setattr(record, column, state)
        seeded_session.flush()

        decision = notification_service.evaluate(seeded_session)

        assert not decision.should_notify
        assert decision.skip_reason == "already_recorded"

    def test_notifies_when_a_record_row_exists_but_no_category_was_touched(self, seeded_session):
        """行だけあって全カテゴリ未入力（集約状態がNULL）の日は「記録済み」と見なさないこと。"""
        today = notification_service.goal_service.resolve_today(seeded_session)
        record_service.ensure_daily_record(seeded_session, today)
        seeded_session.flush()

        assert notification_service.evaluate(seeded_session).should_notify

    def test_uses_the_logical_date_rather_than_the_system_date(self, seeded_session, monkeypatch):
        """境界時刻より前の時刻では、前日を対象に判定すること（技術選定書5.3）。"""
        _set_setting(seeded_session, CALENDAR_DAY_BOUNDARY_HOUR, "4")
        system_now = dt.datetime(2026, 9, 14, 1, 30)
        expected_logical_date = dt.date(2026, 9, 13)

        class _FrozenDatetime(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return system_now

        monkeypatch.setattr(
            notification_service.goal_service.calendar_service.dt, "datetime", _FrozenDatetime
        )
        # 論理日（前日）を除外日にする。システム日付側を見ていれば通知される。
        seeded_session.add(
            CalendarDayOverride(target_date=expected_logical_date, day_type=DayType.OFF)
        )
        seeded_session.flush()

        decision = notification_service.evaluate(seeded_session)

        assert decision.logical_date == expected_logical_date
        assert not decision.should_notify
        assert decision.skip_reason == "day_type_off"


class TestMessageKeys:
    def test_returns_the_pair_when_notifying(self):
        decision = notification_service.NotificationDecision(
            True, dt.date(2026, 9, 13), title_key="t", body_key="b"
        )
        assert decision.message_keys() == ("t", "b")

    def test_raises_when_not_notifying(self):
        decision = notification_service.NotificationDecision(
            False, dt.date(2026, 9, 13), skip_reason="disabled"
        )
        with pytest.raises(ValueError):
            decision.message_keys()
