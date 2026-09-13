"""アプリアイコンの配置先の解決（Phase37）。

exe のアイコン・トレイのアイコン・通知の送信元アイコンは同じ`.ico`を使う。参照する箇所が
3つあるため、パスの組み立てをここへ集約する（CLAUDE.md DRYの原則）。
"""

from __future__ import annotations

from pathlib import Path

from app.config import BACKEND_DIR, resolve_bundled_path
from app.constants.bundle import ASSETS_DIR_NAME, ICON_FILE_NAME


def resolve_icon_path() -> Path:
    """アプリアイコン（`.ico`）の配置先を返す（配布パッケージ対応）。

    返り値:
        アイコンのパス。配布パッケージでは同梱先、開発環境では
        `backend/app/assets/michinari.ico`。存在確認は呼び出し側が行う
        （アイコンが無くてもアプリの機能は動くため、ここでは例外にしない）。

    使用例:
        >>> resolve_icon_path().name
        'michinari.ico'
    """
    return resolve_bundled_path(
        f"{ASSETS_DIR_NAME}/{ICON_FILE_NAME}",
        BACKEND_DIR / "app" / ASSETS_DIR_NAME / ICON_FILE_NAME,
    )
