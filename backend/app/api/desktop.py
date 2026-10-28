"""デスクトップ常駐の即時反映API（開発Todo リマインド導線 D6〜D8）。

自動起動（`desktop.launch_at_login`）のWindowsレジストリへの反映は、常駐起動時
（`app/desktop/runner.py: run()`）にしか行われない。新規利用者向けの1問案内・
既存利用者向けのダッシュボード案内は、保存した設定を今すぐ反映できないと「オンにした
つもりが次回起動まで効かない」という食い違いになるため、この経路を別に用意する。

サービス層は実行環境（配布パッケージかどうか・レジストリ操作）を知らない方針
（CLAUDE.md「サービス層でのHTTP例外の送出」禁止と同じ整理）のため、ここ（API層）が
`app/desktop/autostart.py`を直接呼ぶ。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.app_setting_keys import DESKTOP_LAUNCH_AT_LOGIN
from app.database import get_db
from app.desktop import autostart
from app.schemas.desktop import DesktopAutostartSyncResult
from app.services import setting_reader

router = APIRouter(tags=["desktop"])


@router.post("/desktop/autostart/sync", response_model=DesktopAutostartSyncResult)
def sync_autostart(session: Session = Depends(get_db)) -> DesktopAutostartSyncResult:
    """保存済みの`desktop.launch_at_login`を読み直し、Windowsレジストリへ今すぐ反映する。"""
    launch_at_login = setting_reader.get_bool(session, DESKTOP_LAUNCH_AT_LOGIN)
    supported = autostart.is_supported()
    try:
        applied = autostart.apply(launch_at_login)
    except OSError:
        applied = False
    return DesktopAutostartSyncResult(
        launch_at_login=launch_at_login, supported=supported, applied=applied
    )
