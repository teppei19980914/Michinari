"""OneDriveロック対策の再試行付きファイル削除（`tests/db_retry.py`）のテスト。

`conftest.py`はモジュールインポート時に副作用（DB削除・環境変数設定・`app.database`の
インポート）を持つため直接テストできない。再試行ロジック自体は`db_retry.py`へ切り出して
あるので、ここでは`Path.unlink`を差し替えて疑似的にロックを再現し、再試行の挙動のみを
検証する（実際の待機時間は`monkeypatch`で`time.sleep`を無効化し、テストを高速に保つ）。
"""

from pathlib import Path

import pytest

from tests.db_retry import unlink_retrying


def test_unlink_retrying_succeeds_immediately_without_lock(tmp_path, monkeypatch):
    """ロックがなければ即座に削除され、待機は発生しない。"""
    target = tmp_path / "no_lock.db"
    target.write_text("dummy")
    sleep_calls: list[float] = []
    monkeypatch.setattr("tests.db_retry.time.sleep", lambda seconds: sleep_calls.append(seconds))

    unlink_retrying(target, attempts=5, delay_seconds=3.0)

    assert not target.exists()
    assert sleep_calls == []


def test_unlink_retrying_recovers_after_transient_permission_error(tmp_path, monkeypatch):
    """一時的な`PermissionError`は指定回数以内なら再試行の末に成功する。"""
    target = tmp_path / "locked_then_freed.db"
    target.write_text("dummy")

    real_unlink = Path.unlink
    call_count = {"n": 0}

    def flaky_unlink(self, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise PermissionError("[WinError 32] 別のプロセスが使用中です。")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    sleep_calls: list[float] = []
    monkeypatch.setattr("tests.db_retry.time.sleep", lambda seconds: sleep_calls.append(seconds))

    unlink_retrying(target, attempts=5, delay_seconds=3.0)

    assert call_count["n"] == 3
    # 3回目で成功するため待機は2回（1・2回目の失敗後のみ）で、間隔は指定値どおり。
    assert sleep_calls == [3.0, 3.0]


def test_unlink_retrying_reraises_after_exhausting_attempts(tmp_path, monkeypatch):
    """指定回数を使い切ってもロックが解消しなければ`PermissionError`を送出する。"""
    target = tmp_path / "always_locked.db"
    target.write_text("dummy")

    def always_locked(self, *args, **kwargs):
        raise PermissionError("[WinError 32] 別のプロセスが使用中です。")

    monkeypatch.setattr(Path, "unlink", always_locked)
    sleep_calls: list[float] = []
    monkeypatch.setattr("tests.db_retry.time.sleep", lambda seconds: sleep_calls.append(seconds))

    with pytest.raises(PermissionError):
        unlink_retrying(target, attempts=3, delay_seconds=3.0)

    # 3回試行し、3回目は失敗しても再試行せず送出するため待機は2回のみ。
    assert sleep_calls == [3.0, 3.0]
