"""記録リマインドの常駐スケジューラ（実装スコープC、Phase37）。

**バックエンドと同一プロセス内のデーモンスレッド**として動く。別プロセス（タスク
スケジューラ登録や常駐ヘルパー）を増やさないのは、増やすと「アプリを終了したのに何かが
残っている」状態を利用者に説明しなければならなくなるためである。

やることは「一定間隔で目を覚まし、通知時刻をまたいだかを見る」だけで、通知すべきかの
判定そのものは`app/services/notification_service.py`にある。
"""

from __future__ import annotations

import datetime as dt
import logging
import threading
from collections.abc import Callable

from app.constants.app_setting_keys import DESKTOP_NOTIFICATION_CHECK_INTERVAL_SECONDS
from app.database import SessionLocal
from app.services import notification_service, setting_reader

logger = logging.getLogger(__name__)

#: 設定の読み出しに失敗した場合に使う確認間隔（秒）。`app_setting`が壊れていても
#: スケジューラのループ自体は回し続け、次回の読み出しで復帰できるようにするための下限値。
FALLBACK_CHECK_INTERVAL_SECONDS = 60


class ReminderScheduler:
    """通知時刻の到来を監視し、条件を満たせば通知を出す常駐スレッド。

    使用例:
        >>> scheduler = ReminderScheduler(notify)  # doctest: +SKIP
        >>> scheduler.start()  # doctest: +SKIP
        >>> scheduler.stop()  # doctest: +SKIP
    """

    def __init__(
        self,
        notify: Callable[[notification_service.NotificationDecision], None],
        *,
        now: Callable[[], dt.datetime] = dt.datetime.now,
    ) -> None:
        """
        引数:
            notify: 通知を出す処理。判定結果を受け取る。
            now: 現在日時を返す関数（テストから差し替えるために引数で受け取る）。
        """
        self._notify = notify
        self._now = now
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        # 起動時点を「前回確認した時刻」とすることで、起動より前に過ぎている当日の通知時刻を
        # 蒸し返さない（`notification_service.has_crossed_notification_time`のdocstring参照）。
        self._previous_check = now()
        #: 同じ論理日に二重で通知しないための記録。時計の手動調整などで通知時刻を複数回
        #: またいでも、その日1回に留める。
        self._notified_date: dt.date | None = None

    def start(self) -> None:
        """監視スレッドを開始する（デーモンスレッドのため、終了時に取り残されない）。"""
        self._thread = threading.Thread(target=self._run, name="reminder-scheduler", daemon=True)
        self._thread.start()
        logger.info("記録リマインドの監視を開始しました")

    def stop(self) -> None:
        """監視スレッドの停止を要求する。"""
        self._stop_event.set()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            interval = self._read_check_interval()
            if self._stop_event.wait(interval):
                return
            self.tick()

    def _read_check_interval(self) -> int:
        """確認間隔（秒）を`app_setting`から読み出す。読めなければフォールバック値を使う。"""
        session = SessionLocal()
        try:
            return setting_reader.get_int(session, DESKTOP_NOTIFICATION_CHECK_INTERVAL_SECONDS)
        except Exception:
            logger.exception("確認間隔を読み出せませんでした。既定値で継続します")
            return FALLBACK_CHECK_INTERVAL_SECONDS
        finally:
            session.close()

    def tick(self) -> bool:
        """1回分の確認を行う（ループから毎回呼ばれる。テストからも直接呼べる）。

        例外を外へ出さないのは、1回の失敗でスケジューラのスレッドが死ぬと、以後の通知が
        黙って止まってしまうためである（利用者からは「通知が来ない」としか見えない）。

        返り値:
            実際に通知を出したなら True。
        """
        now = self._now()
        try:
            return self._check(now)
        except Exception:
            logger.exception("記録リマインドの確認に失敗しました")
            return False
        finally:
            self._previous_check = now

    def _check(self, now: dt.datetime) -> bool:
        """通知時刻の到来と通知条件を順に確かめ、満たしていれば通知する。"""
        session = SessionLocal()
        try:
            notify_at = notification_service.read_notification_time(session)
            if not notification_service.has_crossed_notification_time(
                notify_at, self._previous_check, now
            ):
                return False

            decision = notification_service.evaluate(session)
            if not decision.should_notify:
                logger.info("記録リマインドは見送りました: reason=%s", decision.skip_reason)
                return False
            if self._notified_date == decision.logical_date:
                logger.info("記録リマインドは通知済みです: date=%s", decision.logical_date)
                return False

            self._notify(decision)
            self._notified_date = decision.logical_date
            return True
        finally:
            session.close()
