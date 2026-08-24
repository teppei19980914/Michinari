"""認証状態の管理（設計書 ロジック・プロンプト編16.2、データ構造編5.8）。

PAT（Personal Access Token）を主経路とする。PAT未設定・無効時のみ、設定画面から
ブラウザ経由のフォールバック認証フローを提供する。ブラウザ起動と待機を伴うため
バックグラウンドスレッドで実行し、APIスレッドをブロックしない（16.2）。
"""

import threading
from dataclasses import dataclass, field

from newtonx_adk.auth import AuthManager
from newtonx_adk.config import ConfigManager
from sqlalchemy.orm import Session

from app.ai import client as ai_client


@dataclass
class _LoginState:
    in_progress: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


#: フォールバック認証の進行状況（単一利用者・単一プロセスのローカル動作が前提のため、
#: プロセス内の共有状態として保持する。データ構造編6.1「認証なし（単一利用者、ローカル動作）」）。
_state = _LoginState()


@dataclass(frozen=True)
class AiStatusSnapshot:
    authenticated: bool
    model_status: dict[str, bool]
    login_in_progress: bool


def get_status(session: Session) -> AiStatusSnapshot:
    """認証状態とAI基盤の稼働状況を取得する（データ構造編6.2 GET /ai/status）。"""
    authenticated = ai_client.is_authenticated(session)
    model_status: dict[str, bool] = {}
    if authenticated:
        try:
            model_status = ai_client.get_model_status(session)
        except Exception:  # noqa: BLE001 - 稼働状況の取得失敗で状態確認自体を失敗させない（16.7）
            model_status = {}
    return AiStatusSnapshot(
        authenticated=authenticated,
        model_status=model_status,
        login_in_progress=_state.in_progress,
    )


def register_pat(session: Session, *, host: str | None, personal_access_token: str) -> bool:
    """Host・PATを開発キットの設定へ反映する（16.2「設定画面からのPAT登録」）。

    戻り値は反映直後の認証状態。PAT・トークンはapp_settingへ保存しない（5.8）。
    """
    config_manager = ConfigManager()
    snapshot = ai_client.read_config_snapshot(session)
    if host:
        snapshot["host"] = host
    snapshot["personal_access_token"] = personal_access_token
    ai_client.apply_config_snapshot(config_manager, snapshot)
    return AuthManager(config_manager).is_authenticated()


def start_fallback_login(session: Session) -> bool:
    """フォールバック認証（ブラウザ経由）をバックグラウンドスレッドで開始する（16.2）。

    既に進行中の場合は何もしない。戻り値は新規に開始したかどうか。
    """
    with _state.lock:
        if _state.in_progress:
            return False
        _state.in_progress = True

    snapshot = ai_client.read_config_snapshot(session)

    def _run() -> None:
        try:
            ai_client.start_browser_login(snapshot)
        except Exception:  # noqa: BLE001 - 失敗理由はGET /ai/statusの再ポーリングで確認する
            pass
        finally:
            with _state.lock:
                _state.in_progress = False

    threading.Thread(target=_run, daemon=True).start()
    return True


def logout(session: Session) -> None:
    """トークンを破棄する（データ構造編6.2 POST /ai/logout）。"""
    ai_client.logout(session)
