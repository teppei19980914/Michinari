"""デスクトップ常駐・自動起動の即時反映API用スキーマ（開発Todo リマインド導線 D6〜D8）。"""

from __future__ import annotations

from pydantic import BaseModel


class DesktopAutostartSyncResult(BaseModel):
    """`POST /desktop/autostart/sync`の結果。

    属性:
        launch_at_login: 反映を試みた時点で保存されていた設定値。
        supported: 自動起動の登録が意味を持つ実行形態（配布パッケージ）か。
            `False`の場合、`applied`も必ず`False`になる（開発環境のため何もしていない。
            失敗ではない）。
        applied: Windowsレジストリへ実際に反映できたか。
    """

    launch_at_login: bool
    supported: bool
    applied: bool
