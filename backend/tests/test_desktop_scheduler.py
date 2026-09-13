"""ReminderScheduler のテスト（記録リマインドの常駐監視、Phase37）。

ループが毎回呼ぶ1回分の処理（`tick`）を直接動かすほか、スレッドの起動・停止まで通す。
押さえたい振る舞いは次のとおり。

1. 通知時刻をまたいだときだけ通知する
2. 同じ論理日に二重で通知しない（ただし翌日には再び通知する）
3. 1回の失敗でスケジューラが止まらない（例外を外へ出さない）
4. 「終了」で監視スレッドが止まる
"""

import datetime as dt
import time

import pytest

from app.constants.app_setting_keys import (
    DESKTOP_NOTIFICATION_CHECK_INTERVAL_SECONDS,
    DESKTOP_NOTIFICATION_ENABLED,
    DESKTOP_NOTIFICATION_TIME,
)
from app.constants.enums import DayType
from app.desktop import scheduler
from app.models.setting import AppSetting
from app.services import calendar_service, goal_service, notification_service

NOTIFY_TIME = "21:00"
BEFORE = dt.datetime(2026, 9, 13, 20, 59, 30)
AFTER = dt.datetime(2026, 9, 13, 21, 0, 30)


@pytest.fixture
def notified() -> list[notification_service.NotificationDecision]:
    return []


@pytest.fixture
def session_factory(seeded_session, monkeypatch: pytest.MonkeyPatch):
    """スケジューラが内部で開くセッションを、テスト用セッションへ差し替える。

    `SessionLocal()`の戻り値を`close()`されても困らないよう、`close`を無効化した
    薄い代理を返す（テストの後始末はconftestのフィクスチャが行う）。
    """

    class _Proxy:
        def __getattr__(self, name: str):
            return getattr(seeded_session, name)

        def close(self) -> None:
            return None

    monkeypatch.setattr(scheduler, "SessionLocal", lambda: _Proxy())
    # 通知時刻・日種別を実行日に左右されない状態へ固定する。
    seeded_session.get(AppSetting, DESKTOP_NOTIFICATION_TIME).value = NOTIFY_TIME
    today = goal_service.resolve_today(seeded_session)
    calendar_service.set_day_type_override(seeded_session, today, DayType.PLAN, note=None)
    seeded_session.flush()
    return seeded_session


def _build(notified, session_factory, now: dt.datetime) -> scheduler.ReminderScheduler:
    """指定時刻を「現在」とみなすスケジューラを作る（起動時刻＝`BEFORE`固定）。"""
    instance = scheduler.ReminderScheduler(notified.append, now=lambda: BEFORE)
    instance._now = lambda: now
    return instance


class TestTick:
    def test_notifies_when_the_notification_time_is_crossed(self, notified, session_factory):
        instance = _build(notified, session_factory, AFTER)

        assert instance.tick()
        assert len(notified) == 1
        assert notified[0].should_notify

    def test_does_not_notify_before_the_notification_time(self, notified, session_factory):
        instance = _build(notified, session_factory, dt.datetime(2026, 9, 13, 20, 59, 45))

        assert not instance.tick()
        assert notified == []

    def test_does_not_notify_twice_on_the_same_logical_date(self, notified, session_factory):
        """時計の調整などで通知時刻を複数回またいでも、その日は1回に留めること。"""
        instance = _build(notified, session_factory, AFTER)
        assert instance.tick()

        # 前回確認時刻を戻し、同じ日の通知時刻を再度またがせる。
        instance._previous_check = BEFORE
        assert not instance.tick()
        assert len(notified) == 1

    def test_does_not_notify_when_the_decision_says_no(self, notified, session_factory):
        session_factory.get(AppSetting, DESKTOP_NOTIFICATION_ENABLED).value = "false"
        session_factory.flush()
        instance = _build(notified, session_factory, AFTER)

        assert not instance.tick()
        assert notified == []

    def test_swallows_errors_so_the_loop_keeps_running(self, notified, session_factory):
        """1回の失敗でスレッドが死ぬと、以後の通知が黙って止まってしまう。"""
        session_factory.get(AppSetting, DESKTOP_NOTIFICATION_TIME).value = "こわれた値"
        session_factory.flush()
        instance = _build(notified, session_factory, AFTER)

        assert not instance.tick()
        assert notified == []

    def test_advances_the_previous_check_even_when_it_fails(self, notified, session_factory):
        session_factory.get(AppSetting, DESKTOP_NOTIFICATION_TIME).value = "こわれた値"
        session_factory.flush()
        instance = _build(notified, session_factory, AFTER)

        instance.tick()

        assert instance._previous_check == AFTER


class TestReadCheckInterval:
    def test_reads_the_configured_interval(self, notified, session_factory):
        session_factory.get(AppSetting, DESKTOP_NOTIFICATION_CHECK_INTERVAL_SECONDS).value = "30"
        session_factory.flush()
        instance = _build(notified, session_factory, AFTER)

        assert instance._read_check_interval() == 30

    def test_falls_back_when_the_setting_cannot_be_read(self, notified, session_factory):
        session_factory.get(
            AppSetting, DESKTOP_NOTIFICATION_CHECK_INTERVAL_SECONDS
        ).value = "数値ではない"
        session_factory.flush()
        instance = _build(notified, session_factory, AFTER)

        assert instance._read_check_interval() == scheduler.FALLBACK_CHECK_INTERVAL_SECONDS


class TestLifecycle:
    """監視スレッドの起動・停止（Phase37）。

    「終了」を選んでもスレッドが止まらない不具合は、`tick` のテストでは捕まらない。
    `_stop_event.wait` を `time.sleep` へ書き換えても通ってしまうため、実際に起動して
    停止できることをここで確かめる。
    """

    @staticmethod
    def _immediate(instance: scheduler.ReminderScheduler) -> None:
        """確認間隔を0にして、テストが待たされないようにする。"""
        instance._read_check_interval = lambda: 0

    def test_starts_and_stops(self, notified, session_factory):
        instance = _build(notified, session_factory, AFTER)
        self._immediate(instance)

        instance.start()
        instance.stop()
        instance._thread.join(timeout=5)

        assert not instance._thread.is_alive()

    def test_uses_a_daemon_thread_so_it_never_holds_the_process_open(
        self, notified, session_factory
    ):
        """サーバスレッドと違い、こちらは取り残されてもプロセスを止めない側にする。"""
        instance = _build(notified, session_factory, AFTER)
        self._immediate(instance)

        instance.start()
        try:
            assert instance._thread.daemon
        finally:
            instance.stop()
            instance._thread.join(timeout=5)

    def test_keeps_checking_until_stopped(self, notified, session_factory):
        """ループが1回で抜けてしまわないこと（通知が一度きりになる退化を防ぐ）。"""
        instance = _build(notified, session_factory, BEFORE)
        self._immediate(instance)
        ticks: list[bool] = []
        instance.tick = lambda: ticks.append(True) or False

        instance.start()
        for _ in range(200):
            if len(ticks) >= 3:
                break
            time.sleep(0.01)
        instance.stop()
        instance._thread.join(timeout=5)

        assert len(ticks) >= 3


class TestNextDay:
    """翌日には再び通知されること（Phase37）。

    同日の二重通知抑止だけを見ていると、`_notified_date` が一度でも入ったら二度と通知
    しない退化（＝一生に一度しか通知しない）を見逃す。

    論理的な本日は`goal_service.resolve_today`がシステム時計から決めるため、翌日へ
    進めるにはシステム時計ごと固定する必要がある（スケジューラへ渡す`now`だけを進めても
    判定側の日付は変わらない）。
    """

    def test_notifies_again_on_the_following_day(
        self, notified, session_factory, monkeypatch: pytest.MonkeyPatch
    ):
        instance = _build(notified, session_factory, AFTER)
        assert instance.tick()
        first_date = notified[0].logical_date

        next_day = first_date + dt.timedelta(days=1)
        calendar_service.set_day_type_override(session_factory, next_day, DayType.PLAN, note=None)
        session_factory.flush()

        class _FrozenDatetime(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return dt.datetime.combine(next_day, dt.time(21, 0, 30))

        monkeypatch.setattr(calendar_service.dt, "datetime", _FrozenDatetime)
        instance._previous_check = dt.datetime.combine(next_day, dt.time(20, 59, 30))
        instance._now = lambda: dt.datetime.combine(next_day, dt.time(21, 0, 30))

        assert instance.tick()
        assert len(notified) == 2
        assert notified[1].logical_date == next_day
