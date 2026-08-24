"""呼び出し頻度の制御（設計書 ロジック・プロンプト編16.4）。

直近の呼び出し時刻を保持し、経過時間が ai.min_interval_seconds 未満の場合は
差分だけ待機してから送信する。週次要約の遡及生成のように複数回の呼び出しが
連続する場面で特に重要となる（16.4）。
"""

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class RateLimiter:
    """呼び出し間隔の制御状態。プロセス内で共有する単一インスタンスを既定とする。"""

    last_call_at: float | None = None

    def wait_for_interval(
        self,
        min_interval_seconds: int,
        *,
        now: float | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """直近の呼び出しからmin_interval_seconds未満なら待機し、呼び出し時刻を更新する。"""
        current = now if now is not None else time.monotonic()
        if self.last_call_at is not None:
            elapsed = current - self.last_call_at
            remaining = min_interval_seconds - elapsed
            if remaining > 0:
                sleep(remaining)
                current = now if now is not None else time.monotonic()
        self.last_call_at = current

    def reset(self) -> None:
        """テスト間の状態リークを防ぐためのリセット（本番コードからは通常呼ばない）。"""
        self.last_call_at = None


#: プロセス内で共有する既定のレートリミッタ（呼び出し元をまたいで間隔を守るため単一化する）。
default_limiter = RateLimiter()


def wait_for_interval(min_interval_seconds: int) -> None:
    """既定のレートリミッタで待機する（呼び出し側の共通窓口）。"""
    default_limiter.wait_for_interval(min_interval_seconds)
