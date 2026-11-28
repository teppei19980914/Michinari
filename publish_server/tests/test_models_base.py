"""app/models/base.py のテスト（`ensure_utc`の両分岐を直接検証、test-coverage-reviewer
レビュー2026-11-28 MEDIUM指摘。統合テスト経由ではDB再読込で常にnaiveになり、
aware分岐が実質到達しない可能性があったため、ユニットテストで明示的に両方を確認する）。
"""

from datetime import UTC, datetime

from app.models.base import ensure_utc, utcnow


def test_ensure_utc_attaches_utc_to_naive_datetime():
    naive = datetime(2026, 11, 28, 12, 0, 0)
    assert naive.tzinfo is None

    result = ensure_utc(naive)

    assert result.tzinfo is UTC
    assert result.replace(tzinfo=None) == naive


def test_ensure_utc_returns_aware_datetime_unchanged():
    aware = datetime.now(UTC)

    result = ensure_utc(aware)

    assert result is aware


def test_utcnow_returns_aware_datetime():
    assert utcnow().tzinfo is not None
