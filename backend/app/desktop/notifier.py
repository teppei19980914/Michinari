"""デスクトップ通知（トースト）の送出（実装スコープC、Phase37）。

通知ライブラリは`windows-toasts`（Apache-2.0）を使う。Windowsの通知APIを**同一プロセス内
から直接**呼ぶため、通知のたびに別プロセス（PowerShell等）を起動しない。またクリックの
コールバックが自プロセスで発火するため、「通知をクリックしたら記録画面を開く」を
プロトコル登録なしで実現できる。

**AppUserModelIDの登録が要る。** Microsoft公式（「How to enable desktop toast notifications
through an AppUserModelID」）は「スタートメニュー（または All Programs）にAppUserModelIDを
持つ有効なショートカットが無ければ、デスクトップアプリからトーストを発報できません」と
明記している。ここでは同じ登録をレジストリ（HKEY_CURRENT_USER配下）で行う。理由と検証結果は
`app/constants/desktop.py`の`AUMID_REGISTRY_KEY`のコメントに記した。

通知の文面は`frontend/src/locales/ja.json`から引く（CLAUDE.md「文字列リテラルの直接記述」
禁止）。本モジュールは受け取った文字列を表示するだけで、文面そのものを持たない。
"""

from __future__ import annotations

import logging
import winreg
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

from windows_toasts import InteractableWindowsToaster, Toast, ToastDisplayImage

from app.constants.desktop import (
    APP_USER_MODEL_ID,
    AUMID_DISPLAY_NAME_VALUE,
    AUMID_ICON_URI_VALUE,
    AUMID_REGISTRY_KEY_TEMPLATE,
)

logger = logging.getLogger(__name__)


def register_app_user_model_id(
    display_name: str,
    icon_path: Path | None = None,
    registry: ModuleType = winreg,
    *,
    app_user_model_id: str = APP_USER_MODEL_ID,
) -> None:
    """通知の送信元としてAppUserModelIDをWindowsへ登録する。

    毎回の起動で書き直すのは、利用者がアプリのフォルダを移動してもアイコンのパスが
    追随するようにするためである（インストーラを持たないため、登録の機会が起動時しかない）。
    管理者権限は不要（HKEY_CURRENT_USER配下）。

    引数:
        display_name: 通知に表示される送信元の名前。
        icon_path: 送信元アイコン（`.ico`）。存在しない場合は登録を省略する。
        registry: `winreg`互換のモジュール（テストから差し替えるために引数で受け取る）。
        app_user_model_id: 登録する識別子。既定はアプリ固有の値。
    """
    key_path = AUMID_REGISTRY_KEY_TEMPLATE.format(app_user_model_id=app_user_model_id)
    with registry.CreateKeyEx(
        registry.HKEY_CURRENT_USER, key_path, 0, registry.KEY_SET_VALUE
    ) as key:
        registry.SetValueEx(key, AUMID_DISPLAY_NAME_VALUE, 0, registry.REG_SZ, display_name)
        if icon_path is not None and icon_path.is_file():
            registry.SetValueEx(key, AUMID_ICON_URI_VALUE, 0, registry.REG_SZ, str(icon_path))


class ToastNotifier:
    """Windowsのトースト通知を出す。

    生成時にAppUserModelIDの登録を行うため、**通知を出す前に1度だけ生成して使い回す**
    （毎回生成してもよいが、レジストリ書き込みが無駄に増える）。

    使用例:
        >>> notifier = ToastNotifier("ミチナリ")  # doctest: +SKIP
        >>> notifier.show("今日の記録はまだです", "3分で終わります")  # doctest: +SKIP
    """

    def __init__(
        self,
        source_name: str,
        icon_path: Path | None = None,
        registry: ModuleType = winreg,
        *,
        app_user_model_id: str = APP_USER_MODEL_ID,
    ) -> None:
        """
        引数:
            source_name: 通知に表示される送信元の名前。
            icon_path: 通知へ添えるアイコン（`.ico`）。
            registry: `winreg`互換のモジュール。
            app_user_model_id: 使用する識別子。
        """
        self._icon_path = icon_path
        register_app_user_model_id(
            source_name, icon_path, registry, app_user_model_id=app_user_model_id
        )
        self._toaster = InteractableWindowsToaster(source_name, notifierAUMID=app_user_model_id)

    def show(self, title: str, body: str, on_click: Callable[[], None] | None = None) -> None:
        """トーストを1件表示する。

        引数:
            title: 見出し（1行目）。
            body: 本文（2行目）。
            on_click: 通知をクリックしたときに呼ぶ処理。アプリが終了した後に
                通知センターから押された場合は呼ばれない（プロセスが居ないため）。
        """
        toast = Toast(text_fields=[title, body])
        if on_click is not None:
            toast.on_activated = lambda _args: on_click()
        if self._icon_path is not None and self._icon_path.is_file():
            toast.AddImage(ToastDisplayImage.fromPath(self._icon_path))
        self._toaster.show_toast(toast)
        logger.info("通知を表示しました: %s", title)
