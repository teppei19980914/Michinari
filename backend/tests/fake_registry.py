"""テスト用の`winreg`代替（Phase37）。

自動起動の登録（`app/desktop/autostart.py`）とAppUserModelIDの登録
（`app/desktop/notifier.py`）は、どちらも`winreg`互換のモジュールを引数で受け取る。
テストで実際のレジストリを書き換えると開発端末の設定を壊すため、同じ形の偽物をここに置く。

2つのテストファイルから使うため、片方へ書かずに独立したモジュールとする
（CODING_RULES.md DRYの原則）。
"""

from __future__ import annotations

from typing import Any

#: `winreg`の定数に対応する値。実際の値と一致している必要はなく、同一性だけが意味を持つ。
HKEY_CURRENT_USER = "HKEY_CURRENT_USER"
KEY_READ = 0x20019
KEY_SET_VALUE = 0x00002
REG_SZ = 1


class _FakeKey:
    """`winreg`のキーハンドルに相当する。`with`で使えるようにしている。"""

    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values

    def __enter__(self) -> _FakeKey:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        return None


class FakeRegistry:
    """`winreg`のうち、本アプリが使う関数だけを備えた偽物。

    使用例:
        >>> registry = FakeRegistry()
        >>> with registry.CreateKeyEx(HKEY_CURRENT_USER, "A", 0, KEY_SET_VALUE) as key:
        ...     registry.SetValueEx(key, "Name", 0, REG_SZ, "value")
        >>> registry.keys["A"]["Name"]
        'value'
    """

    HKEY_CURRENT_USER = HKEY_CURRENT_USER
    KEY_READ = KEY_READ
    KEY_SET_VALUE = KEY_SET_VALUE
    REG_SZ = REG_SZ

    def __init__(self, keys: dict[str, dict[str, Any]] | None = None) -> None:
        #: キーのパス → 値名 → 値。
        self.keys: dict[str, dict[str, Any]] = keys if keys is not None else {}

    def CreateKeyEx(self, _root: str, path: str, _reserved: int, _access: int) -> _FakeKey:  # noqa: N802 (winregの名前に合わせる)
        """キーを作る（既にあればそれを返す）。"""
        return _FakeKey(self.keys.setdefault(path, {}))

    def OpenKey(self, _root: str, path: str, _reserved: int, _access: int) -> _FakeKey:  # noqa: N802 (同上)
        """既存のキーを開く。無ければ`FileNotFoundError`（`winreg`と同じ`OSError`の一種）。"""
        if path not in self.keys:
            raise FileNotFoundError(path)
        return _FakeKey(self.keys[path])

    def SetValueEx(  # noqa: N802 (同上)
        self, key: _FakeKey, name: str, _reserved: int, _value_type: int, value: Any
    ) -> None:
        """値を書き込む。"""
        key.values[name] = value

    def QueryValueEx(self, key: _FakeKey, name: str) -> tuple[Any, int]:  # noqa: N802 (同上)
        """値を読み出す。無ければ`FileNotFoundError`。"""
        if name not in key.values:
            raise FileNotFoundError(name)
        return key.values[name], REG_SZ

    def DeleteValue(self, key: _FakeKey, name: str) -> None:  # noqa: N802 (同上)
        """値を削除する。無ければ`FileNotFoundError`。"""
        if name not in key.values:
            raise FileNotFoundError(name)
        del key.values[name]
