"""「今日」の論理日算出（D-09）の単体テスト。実時間に依存させず、境界時刻の両分岐を
明示的に検証する（CODING_RULES.md「バックエンドの実時間レースに注意する」と同じ方針）。
"""

from datetime import UTC, date, datetime

from app.services import calendar_service


def test_resolve_logical_today_returns_previous_day_before_boundary_hour():
    now = datetime(2026, 11, 28, 3, 0, tzinfo=UTC)

    result = calendar_service.resolve_logical_today(now, boundary_hour=5)

    assert result == date(2026, 11, 27)


def test_resolve_logical_today_returns_same_day_at_or_after_boundary_hour():
    now = datetime(2026, 11, 28, 5, 0, tzinfo=UTC)

    result = calendar_service.resolve_logical_today(now, boundary_hour=5)

    assert result == date(2026, 11, 28)
