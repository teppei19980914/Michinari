"""開発キット（NewtonX ADK）のラッパ（設計書 ロジック・プロンプト編16.1〜16.2）。

開発キットの仕様は変更できないため、`myvenv/Lib/site-packages/newtonx_adk/` の
実装済みソースコード（`client.py`・`auth.py`・`config.py`・`exceptions.py`）を確認して
実装する（CLAUDE.md 情報源の信頼性ルール：ハルシネーション防止のため公式ドキュメントより
実装済みソースコードを優先。公式ドキュメント記載の `send_message` の `parent_order` 引数は
実装コードに存在しないため使用しない。実装フェーズ分割計画書 Phase5 16.3.1参照）。

認証情報（PAT等）はここでは保存しない。開発キットの設定（ConfigManager、
`~/.newtonx/config.json`）に委ねる（データ構造編5.8）。
"""

import time
from dataclasses import dataclass

from newtonx_adk.auth import AuthManager
from newtonx_adk.client import NewtonXClient
from newtonx_adk.config import ConfigManager
from newtonx_adk.exceptions import (
    APIError,
    AuthenticationError,
    ChatError,
    ConfigurationError,
    FileUploadError,
    NewtonXError,
)
from sqlalchemy.orm import Session

from app.ai.exceptions import AiAuthRequiredError, AiConfigError, AiError, AiTimeoutError
from app.constants.app_setting_keys import (
    AI_API_BASE_URL,
    AI_CLIENT_ID,
    AI_HOST,
    AI_MAX_RETRIES,
    AI_TENANT_ID,
    AI_TIMEOUT_SECONDS,
)
from app.services import setting_reader

#: タイムアウトを示す文字列（16.6「エラーメッセージにタイムアウトを示す文字列が含まれるか」）。
#: requests/開発キットが実際に発するメッセージに合わせて判定する（timeoutは英語表記のみ）。
_TIMEOUT_MESSAGE_MARKERS = ("timeout", "timed out")

#: send_messageが常に失敗することを実機確認済みのアシスタント名（設計書 データ構造編6.2、
#: 仕様書8.9.1、実装フェーズ分割計画書Phase5前提）。将来この一覧は変動しうるため、
#: 本リストのみに依存せず、送信失敗時の汎用エラーハンドリング（_translate_error による
#: AI_ERROR化）と併用する設計とする。
_UNSUPPORTED_ASSISTANT_NAMES = frozenset({"GPT-4o mini", "GPT-4o"})


@dataclass(frozen=True)
class SendResult:
    """メッセージ送信結果（通信ログ記録用、16.8）。"""

    response_text: str
    latency_ms: int


def read_config_snapshot(session: Session) -> dict[str, object]:
    """app_settingから開発キット設定への反映用スナップショットを読み出す（16.1）。

    バックグラウンドスレッドで実行する処理（フォールバック認証、16.2）へは
    SQLAlchemy Session をそのまま渡せない（スレッドセーフでないため）ため、
    プレーンな dict に変換して受け渡す。
    PAT（personal_access_token）はapp_settingに保存しない値のため対象外とする（5.8）。
    """
    snapshot: dict[str, object] = {
        "timeout": setting_reader.get_int(session, AI_TIMEOUT_SECONDS),
        "max_retries": setting_reader.get_int(session, AI_MAX_RETRIES),
    }
    host = setting_reader.get_str(session, AI_HOST).strip()
    if host:
        snapshot["host"] = host
    client_id = setting_reader.get_str(session, AI_CLIENT_ID).strip()
    if client_id:
        snapshot["client_id"] = client_id
    tenant_id = setting_reader.get_str(session, AI_TENANT_ID).strip()
    if tenant_id:
        snapshot["tenant_id"] = tenant_id
    api_base_url = setting_reader.get_str(session, AI_API_BASE_URL).strip()
    if api_base_url:
        snapshot["api_base_url"] = api_base_url
    return snapshot


def apply_config_snapshot(config_manager: ConfigManager, snapshot: dict[str, object]) -> None:
    """read_config_snapshot() が返したスナップショットを開発キットの設定へ反映する（16.1）。"""
    config_manager.update_config(**snapshot)


def build_client(session: Session) -> NewtonXClient:
    """app_settingの設定を反映した開発キットクライアントを構築する（16.1手順）。"""
    config_manager = ConfigManager()
    apply_config_snapshot(config_manager, read_config_snapshot(session))
    return NewtonXClient(config_manager)


def _translate_error(exc: Exception, *, elapsed_seconds: float, timeout_seconds: int) -> Exception:
    """開発キット例外をドメイン例外へ変換する（16.6の対応表）。

    タイムアウト専用の例外クラスは存在しないため（16.6実装上の注意）、経過時間または
    エラーメッセージの文字列判定でAI_TIMEOUTを判定する。
    """
    if isinstance(exc, AuthenticationError):
        return AiAuthRequiredError(str(exc))
    if isinstance(exc, ConfigurationError):
        return AiConfigError(str(exc))
    if isinstance(exc, (APIError, ChatError, FileUploadError, NewtonXError)):
        message = str(exc).lower()
        if elapsed_seconds >= timeout_seconds or any(
            marker in message for marker in _TIMEOUT_MESSAGE_MARKERS
        ):
            return AiTimeoutError(str(exc))
        return AiError(f"{exc}（時間をおいて再試行してください）")
    return AiError(str(exc))


def is_authenticated(session: Session) -> bool:
    """認証状態を確認する（16.2「起動時：Host・PATが設定済みかを確認する」）。"""
    config_manager = ConfigManager()
    apply_config_snapshot(config_manager, read_config_snapshot(session))
    return AuthManager(config_manager).is_authenticated()


def get_model_status(session: Session) -> dict[str, bool]:
    """モデルの利用可否を取得する（16.1「稼働確認：起動時にモデルの利用可否を取得する」）。"""
    client = build_client(session)
    timeout_seconds = setting_reader.get_int(session, AI_TIMEOUT_SECONDS)
    started = time.monotonic()
    try:
        return client.get_model_status()
    except Exception as exc:  # noqa: BLE001 - 開発キット例外を一律ドメイン例外へ変換するため捕捉
        raise _translate_error(
            exc, elapsed_seconds=time.monotonic() - started, timeout_seconds=timeout_seconds
        ) from exc


def get_assistants(session: Session) -> list[dict]:
    """アシスタント一覧を取得する（データ構造編6.2 GET /ai/assistants）。

    送信が常に失敗することを確認済みのアシスタント（GPT-4o mini・GPT-4o）は
    選択肢から除外する（データ構造編6.2、仕様書8.9.1）。
    """
    client = build_client(session)
    timeout_seconds = setting_reader.get_int(session, AI_TIMEOUT_SECONDS)
    started = time.monotonic()
    try:
        assistants = client.get_assistants()
    except Exception as exc:  # noqa: BLE001
        raise _translate_error(
            exc, elapsed_seconds=time.monotonic() - started, timeout_seconds=timeout_seconds
        ) from exc
    return [
        assistant
        for assistant in assistants
        if assistant.get("name") not in _UNSUPPORTED_ASSISTANT_NAMES
    ]


def create_chat_in_folder_by_name(
    session: Session, *, assistant_uid: str, folder_name: str, title: str
) -> str:
    """フォルダ名を指定してチャットを作成する（存在しない場合は自動作成、16.3手順1）。"""
    client = build_client(session)
    timeout_seconds = setting_reader.get_int(session, AI_TIMEOUT_SECONDS)
    started = time.monotonic()
    try:
        chat_uid = client.create_chat_in_folder_by_name(
            assistant_uid=assistant_uid, folder_name=folder_name, title=title
        )
    except Exception as exc:  # noqa: BLE001
        raise _translate_error(
            exc, elapsed_seconds=time.monotonic() - started, timeout_seconds=timeout_seconds
        ) from exc
    if not chat_uid:
        raise AiError("フォルダ内チャットの作成に失敗しました")
    return chat_uid


def send_message(session: Session, *, chat_uid: str, message: str) -> SendResult:
    """メッセージを送信する。Web検索・ナレッジ検索は明示的に無効化する（16.1手順4、完了条件）。"""
    client = build_client(session)
    timeout_seconds = setting_reader.get_int(session, AI_TIMEOUT_SECONDS)
    started = time.monotonic()
    try:
        response_text = client.send_message(
            chat_uid=chat_uid,
            message=message,
            knowledge_search=False,
            web_search=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise _translate_error(
            exc, elapsed_seconds=time.monotonic() - started, timeout_seconds=timeout_seconds
        ) from exc
    latency_ms = int((time.monotonic() - started) * 1000)
    if response_text is None:
        raise AiError("AI基盤からの応答が空でした")
    return SendResult(response_text=response_text, latency_ms=latency_ms)


def logout(session: Session) -> None:
    """トークンを破棄する（データ構造編6.2 POST /ai/logout）。"""
    config_manager = ConfigManager()
    apply_config_snapshot(config_manager, read_config_snapshot(session))
    AuthManager(config_manager).logout()


def start_browser_login(config_snapshot: dict[str, object]) -> bool:
    """フォールバック認証（ブラウザ経由）を実行する（16.2、PAT未設定・無効時のみ想定）。

    ブラウザ起動と待機を伴うため、呼び出し側（app/ai/auth.py）でバックグラウンドスレッド
    実行すること（APIスレッドをブロックしないため、16.2・データ構造編5.8）。config_snapshot は
    read_config_snapshot() の戻り値をスレッド起動前に読み出して渡す（Session はスレッド間で
    共有できないため）。
    """
    config_manager = ConfigManager()
    apply_config_snapshot(config_manager, config_snapshot)
    client = NewtonXClient(config_manager)
    return client.authenticate()
