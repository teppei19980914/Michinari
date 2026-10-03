"""記録リマインド通知の判定（Phase37）。

「いま通知を出すべきか」「出すならどの文面か」だけをここで決める。実際にトーストを出す
処理・スケジューラのループは`app/desktop/`側にあり、このモジュールはWindowsにもGUIにも
依存しない（CLAUDE.md「サービス層でのHTTP例外の送出」禁止と同じ考え方で、サービス層は
表示手段を知らない）。こうしておくことで、判定の全分岐を通常のテストで検証できる。

判定は仕様（実装スコープC）に従い次のとおり。

| 条件 | 通知 |
| --- | --- |
| `desktop.notification_enabled` が false | 出さない |
| その日が除外日（`DayType.OFF`） | 出さない |
| その日が記録済み（進捗のみ登録済み／報告済みのいずれか） | 出さない |
| その日がバッファ日（`DayType.BUFFER`） | 出す（文面を変える） |
| 上記以外（`DayType.PLAN`） | 出す |

日付は**必ず論理的な本日**（`goal_service.resolve_today`）を使う。システム日付を直接見ると、
1日の境界時刻（`calendar.day_boundary_hour`）を4時に設定している利用者に対して、深夜0〜4時
だけ画面上の「今日」と食い違った判定になる（技術選定書5.3）。
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.constants import locale_keys
from app.constants.app_setting_keys import (
    DESKTOP_NOTIFICATION_ENABLED,
    DESKTOP_NOTIFICATION_TIME,
)
from app.constants.enums import DayType
from app.services import calendar_service, goal_service, record_service, setting_reader
from app.services.exceptions import ValidationError

#: 通知時刻の入力形式（`HH:MM`の24時間表記）。`app_setting`へは文字列で保存するため
#: （データ構造編5.2）、読み出し時にここで検証する。設定画面の`<input type="time">`が
#: 生成する形式と一致させている。
NOTIFICATION_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

#: 日種別ごとの文面（ロケールキー）。`DayType.OFF`は通知しないため対を持たない。
#: 文言そのものは`frontend/src/locales/ja.json`にあり、ここにあるのはキーだけである。
_MESSAGE_KEYS_BY_DAY_TYPE = {
    DayType.PLAN: (locale_keys.NOTIFICATION_PLAN_TITLE, locale_keys.NOTIFICATION_PLAN_BODY),
    DayType.BUFFER: (locale_keys.NOTIFICATION_BUFFER_TITLE, locale_keys.NOTIFICATION_BUFFER_BODY),
}


@dataclass(frozen=True)
class NotificationDecision:
    """通知するか否かと、通知する場合の文面キー。

    属性:
        should_notify: 通知すべきなら True。
        logical_date: 判定に用いた論理的な本日（通知本文のリンク先＝記録画面のURLに使う）。
        title_key: 通知の見出しのロケールキー。`should_notify`が False なら None。
        body_key: 通知の本文のロケールキー。`should_notify`が False なら None。
        skip_reason: 通知しない理由（ログ用の短い識別子）。通知する場合は None。
    """

    should_notify: bool
    logical_date: dt.date
    title_key: str | None = None
    body_key: str | None = None
    skip_reason: str | None = None

    def message_keys(self) -> tuple[str, str]:
        """通知する場合の（見出し, 本文）のロケールキーを返す。

        返り値:
            ロケールキーの組。

        例外:
            ValueError: 通知しないと判定された場合（呼び出し側の取り違え）。

        使用例:
            >>> import datetime as dt
            >>> NotificationDecision(
            ...     True, dt.date(2026, 9, 13), title_key="a", body_key="b"
            ... ).message_keys()
            ('a', 'b')
        """
        if not self.should_notify or self.title_key is None or self.body_key is None:
            raise ValueError("通知しないと判定された結果から文面を取り出そうとしています")
        return self.title_key, self.body_key


def parse_notification_time(value: str) -> dt.time:
    """`app_setting`の`desktop.notification_time`を`time`へ変換する。

    引数:
        value: `"21:00"`形式の文字列。

    返り値:
        対応する`datetime.time`。

    例外:
        ValidationError: 形式が`HH:MM`（24時間表記）でない場合。

    使用例:
        >>> parse_notification_time("21:00")
        datetime.time(21, 0)
    """
    match = NOTIFICATION_TIME_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValidationError("通知する時刻は 00:00 〜 23:59 の形式で指定してください")
    return dt.time(int(match.group(1)), int(match.group(2)))


def has_crossed_notification_time(
    notify_at: dt.time, previous_check: dt.datetime, now: dt.datetime
) -> bool:
    """前回の確認時刻から今回までの間に、通知時刻をまたいだかを返す。

    「またいだ瞬間に1回だけ」を判定に使うことで、確認間隔
    （`desktop.notification_check_interval_seconds`）を短くしても通知が連続しない。

    起動時点で当日の通知時刻を既に過ぎていた場合に通知しないのは、この関数の呼び出し側が
    `previous_check`へ起動時刻を入れるためである（`app/desktop/scheduler.py`）。仕様が
    「設定時刻に通知する」であり、起動した瞬間に何時間も前の予定を蒸し返すのは意図と異なる。

    引数:
        notify_at: 通知する時刻。
        previous_check: 前回確認した日時。
        now: 今回の確認日時。

    返り値:
        またいでいれば True。

    使用例:
        >>> import datetime as dt
        >>> has_crossed_notification_time(
        ...     dt.time(21, 0),
        ...     dt.datetime(2026, 9, 13, 20, 59, 30),
        ...     dt.datetime(2026, 9, 13, 21, 0, 30),
        ... )
        True
    """
    if now <= previous_check:
        # 時刻の巻き戻し（手動での時計調整・スリープ復帰時のずれ）。次回以降で判定する。
        return False
    # 前回と今回が日をまたぐ場合、間に挟まる各日の通知時刻を順に調べる必要がある。
    # 確認間隔は分単位であり、実際に挟まるのは高々1日だが、スリープからの長時間復帰でも
    # 取りこぼさないよう素直に走査する（走査量は経過日数に比例するだけで済む）。
    target_date = previous_check.date()
    while target_date <= now.date():
        target = dt.datetime.combine(target_date, notify_at)
        if previous_check < target <= now:
            return True
        target_date += dt.timedelta(days=1)
    return False


def evaluate(session: Session) -> NotificationDecision:
    """いま記録リマインドを出すべきかを判定する（時刻の判定は呼び出し側で済ませておく）。

    引数:
        session: DBセッション。

    返り値:
        `NotificationDecision`。

    使用例:
        >>> decision = evaluate(session)  # doctest: +SKIP
        >>> decision.should_notify  # doctest: +SKIP
        True
    """
    today = goal_service.resolve_today(session)

    if not setting_reader.get_bool(session, DESKTOP_NOTIFICATION_ENABLED):
        return NotificationDecision(False, today, skip_reason="disabled")

    day_type = calendar_service.resolve_day_type(
        session, today, goal_service.resolve_treat_holiday_as_buffer(session)
    )
    if day_type == DayType.OFF:
        return NotificationDecision(False, today, skip_reason="day_type_off")

    record = record_service.get_daily_record(session, today)
    if record_service.resolve_record_state(record) is not None:
        return NotificationDecision(False, today, skip_reason="already_recorded")

    title_key, body_key = _MESSAGE_KEYS_BY_DAY_TYPE[day_type]
    return NotificationDecision(True, today, title_key=title_key, body_key=body_key)


def read_notification_time(session: Session) -> dt.time:
    """`app_setting`から通知時刻を読み出す（不正な値は既定の解釈へ倒さず例外にする）。

    引数:
        session: DBセッション。

    返り値:
        設定されている通知時刻。

    例外:
        ValidationError: 保存されている値が`HH:MM`形式でない場合。
    """
    return parse_notification_time(setting_reader.get_str(session, DESKTOP_NOTIFICATION_TIME))
