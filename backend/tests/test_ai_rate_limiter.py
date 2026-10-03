"""ai/rate_limiter のテスト（ロジック・プロンプト編16.4 呼び出し頻度の制御）。"""

from app.ai import rate_limiter as rate_limiter_module
from app.ai.rate_limiter import RateLimiter


def test_module_level_wait_for_interval_uses_shared_default_limiter():
    rate_limiter_module.default_limiter.reset()

    rate_limiter_module.wait_for_interval(0)

    assert rate_limiter_module.default_limiter.last_call_at is not None
    rate_limiter_module.default_limiter.reset()


def test_wait_for_interval_does_not_sleep_on_first_call():
    limiter = RateLimiter()
    sleeps: list[float] = []

    limiter.wait_for_interval(2, now=100.0, sleep=sleeps.append)

    assert sleeps == []
    assert limiter.last_call_at == 100.0


def test_wait_for_interval_sleeps_for_remaining_time_when_called_too_soon():
    limiter = RateLimiter()
    limiter.wait_for_interval(2, now=100.0, sleep=lambda s: None)
    sleeps: list[float] = []

    limiter.wait_for_interval(2, now=100.5, sleep=sleeps.append)

    assert sleeps == [1.5]


def test_wait_for_interval_does_not_sleep_when_interval_already_elapsed():
    limiter = RateLimiter()
    limiter.wait_for_interval(2, now=100.0, sleep=lambda s: None)
    sleeps: list[float] = []

    limiter.wait_for_interval(2, now=103.0, sleep=sleeps.append)

    assert sleeps == []
    assert limiter.last_call_at == 103.0


def test_reset_clears_last_call_at():
    limiter = RateLimiter()
    limiter.wait_for_interval(2, now=100.0, sleep=lambda s: None)

    limiter.reset()

    assert limiter.last_call_at is None
