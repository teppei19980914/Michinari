"""Windowsサインイン時の自動起動の登録・解除（実装スコープB、Phase37）。

`HKEY_CURRENT_USER\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run` へ実行ファイルの
パスを書き込む。スタートアップフォルダへショートカット（`.lnk`）を置く方式ではなく
こちらを採る理由は`app/constants/desktop.py`の定数コメントに記した（標準ライブラリ
`winreg`だけで完結し、登録・解除・状態確認のすべてをテストできるため）。

管理者権限は不要（HKEY_CURRENT_USER配下のため）。利用者から見るとタスクマネージャーの
「スタートアップ アプリ」に「Michinari」として現れ、そこからも無効化できる。

**登録できるのは配布パッケージ（exe）として起動している場合だけ**である。ソースから
起動している開発環境では`sys.executable`がPythonインタプリタを指し、それを登録しても
アプリは起動しないため、何もせず警告を記録する。
"""

from __future__ import annotations

import logging
import sys
import winreg
from types import ModuleType

from app.constants.desktop import LAUNCH_AT_LOGIN_REGISTRY_KEY, LAUNCH_AT_LOGIN_VALUE_NAME

logger = logging.getLogger(__name__)


def is_supported() -> bool:
    """自動起動の登録が意味を持つ実行形態かを返す。

    返り値:
        配布パッケージ（PyInstallerでパッケージ化された実行ファイル）なら True。
    """
    return bool(getattr(sys, "frozen", False))


def resolve_launch_command(executable: str | None = None) -> str:
    """Windowsがサインイン時に実行するコマンド文字列を組み立てる。

    パスを二重引用符で囲むのは、インストール先にスペースを含む場合（例:
    `C:\\Users\\山田 太郎\\Michinari\\Michinari.exe`）に、Windowsがパスを途中で区切って
    別の実行ファイルを起動しようとするのを防ぐためである。

    引数:
        executable: 実行ファイルのパス。既定は`sys.executable`。

    返り値:
        引用符で囲んだコマンド文字列。

    使用例:
        >>> resolve_launch_command(r"C:\\Program Files\\Michinari\\Michinari.exe")
        '"C:\\\\Program Files\\\\Michinari\\\\Michinari.exe"'
    """
    return f'"{executable or sys.executable}"'


def is_enabled(registry: ModuleType = winreg) -> bool:
    """現在、自動起動が登録されているかを返す。

    引数:
        registry: `winreg`互換のモジュール（テストから差し替えるために引数で受け取る）。

    返り値:
        登録されていれば True。
    """
    try:
        with registry.OpenKey(
            registry.HKEY_CURRENT_USER, LAUNCH_AT_LOGIN_REGISTRY_KEY, 0, registry.KEY_READ
        ) as key:
            registry.QueryValueEx(key, LAUNCH_AT_LOGIN_VALUE_NAME)
    except OSError:
        # キーが無い・値が無いのいずれも「未登録」を意味する（どちらも正常な状態）。
        return False
    return True


def enable(registry: ModuleType = winreg, *, executable: str | None = None) -> None:
    """自動起動を登録する（既に登録済みなら実行ファイルのパスを最新へ更新する）。

    パスを毎回書き直すのは、利用者がアプリのフォルダを別の場所へ移動した場合に、
    古いパスが残って起動しなくなるのを防ぐためである。

    引数:
        registry: `winreg`互換のモジュール。
        executable: 登録する実行ファイルのパス。既定は`sys.executable`。
    """
    with registry.CreateKeyEx(
        registry.HKEY_CURRENT_USER, LAUNCH_AT_LOGIN_REGISTRY_KEY, 0, registry.KEY_SET_VALUE
    ) as key:
        registry.SetValueEx(
            key,
            LAUNCH_AT_LOGIN_VALUE_NAME,
            0,
            registry.REG_SZ,
            resolve_launch_command(executable),
        )


def disable(registry: ModuleType = winreg) -> None:
    """自動起動の登録を解除する（未登録なら何もしない）。

    引数:
        registry: `winreg`互換のモジュール。
    """
    try:
        with registry.OpenKey(
            registry.HKEY_CURRENT_USER, LAUNCH_AT_LOGIN_REGISTRY_KEY, 0, registry.KEY_SET_VALUE
        ) as key:
            registry.DeleteValue(key, LAUNCH_AT_LOGIN_VALUE_NAME)
    except OSError:
        # 既に解除済み（キーも値も無い）。利用者から見た結果は同じなので成功として扱う。
        return


def apply(enabled: bool, registry: ModuleType = winreg, *, executable: str | None = None) -> bool:
    """設定値（`desktop.launch_at_login`）をWindowsへ反映する。

    引数:
        enabled: 自動起動を有効にするなら True。
        registry: `winreg`互換のモジュール。
        executable: 登録する実行ファイルのパス。既定は`sys.executable`。

    返り値:
        実際に反映したなら True。配布パッケージ以外で実行され、反映を見送った場合は False。
    """
    if not is_supported():
        logger.warning(
            "自動起動の設定はソースからの起動では反映しません（配布パッケージでのみ有効）: "
            "enabled=%s",
            enabled,
        )
        return False
    if enabled:
        enable(registry, executable=executable)
    else:
        disable(registry)
    logger.info("自動起動の登録を更新しました: enabled=%s", enabled)
    return True
