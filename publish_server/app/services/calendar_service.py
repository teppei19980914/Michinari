"""「今日」の論理日の算出（開発Todo_Web公開_v1.0 D-09、単位2）。

クライアント側で論理日を判断しない（CLAUDE.md規約）。ローカル側`calendar_service.
resolve_logical_today`と同じ考え方（境界時刻未満は前日扱い）だが、publish_serverは
複数利用者が同じプロセスを共有するため、利用者ごとの`app_setting`ではなく
サーバ全体の設定値（`app/config.py`の`today_boundary_hour`）を使う。
"""

from datetime import UTC, date, datetime, timedelta


def resolve_logical_today(now: datetime, boundary_hour: int) -> date:
    """`now`はUTC awareであること。`boundary_hour`未満の時刻は前日として扱う。"""
    if now.hour < boundary_hour:
        return (now - timedelta(days=1)).date()
    return now.date()


def resolve_today(boundary_hour: int) -> date:
    return resolve_logical_today(datetime.now(UTC), boundary_hour)
