"""ドメイン例外→エラーコードの対応表のテスト（データ構造編6.3、app/api/errors.py）、および
未分類の例外に対する応答形式のテスト（app/api/errors.py の Exception ハンドラ）。

コード文字列はバックエンド（_STATUS_AND_CODE）・フロント（constants/errorCodes.ts）・
ロケール（locales/ja.json の errors.*）・設計書6.3の4箇所に手書きで並存する。綴りがずれても
実行時例外にならず（画面は既定文言へ黙って落ちる）型検査でも検知できないため、
ここで値そのものを固定する。

DomainErrorでもRequestValidationErrorでもない想定外の例外が、本アプリの
{"error": {"code", "message", "details"}} 形式（データ構造編6.1）でINTERNAL_ERRORとして
返ることも合わせて検証する。これが無いと、フロントのエラー解析（error.codeを前提とする）が
破綻し、利用者に何も表示されない事態になりうる（2026-09-19、非エンジニア向けエラー
表示改善で発見）。

Starlette の ServerErrorMiddleware は、Exception用ハンドラで応答を組み立てて送信した後も
「サーバ側のログ・テストクライアントでの検知のため」常に例外を再送出する仕様（実サーバ
では実害なく、送信済みの応答はそのままクライアントへ届く）。既定の `client` フィクスチャの
TestClientは`raise_server_exceptions=True`のためこの再送出をテスト側の例外として拾って
しまうので、想定外例外のテストのみ`raise_server_exceptions=False`のTestClientを使う。
"""

import inspect
import json
import logging
from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient

from app.ai import auth as ai_auth
from app.api.errors import _STATUS_AND_CODE
from app.main import app
from app.services import exceptions as exceptions_module
from app.services.exceptions import (
    CloseConfirmationRequiredError,
    DomainError,
    InvalidStateTransitionError,
)


def test_close_confirmation_required_has_its_own_code():
    """確認待ちは状態エラーと別コードで返す（2026-09-11の不具合の再発検知）。

    同じコードにすると、画面がクローズ済み目標への再クローズ等を「確認が必要」と誤解し、
    無関係な確認文言を表示したまま本当のエラーを握り潰す。
    """
    assert _STATUS_AND_CODE[CloseConfirmationRequiredError] == (
        status.HTTP_409_CONFLICT,
        "CLOSE_CONFIRMATION_REQUIRED",
    )
    assert (
        _STATUS_AND_CODE[CloseConfirmationRequiredError][1]
        != _STATUS_AND_CODE[InvalidStateTransitionError][1]
    )


def test_every_registered_exception_is_a_domain_error_subclass():
    """未登録のDomainErrorはINTERNAL_ERROR(500)へ落ちるため、登録漏れは静かな500になる。

    対応表の探索は type(exc) の完全一致（継承を辿らない）ため、サブクラスを追加した場合も
    個別に登録する必要がある。ここでは登録済みの型が例外クラスであることだけを固定する。
    """
    for exception_type, (status_code, code) in _STATUS_AND_CODE.items():
        assert issubclass(exception_type, Exception), exception_type
        assert 400 <= status_code < 600, (exception_type, status_code)
        assert code == code.upper(), (exception_type, code)


def test_domain_error_subclasses_used_by_goal_close_are_registered():
    """クローズ処理が送出する例外が両方とも対応表にあること（フォールバック500を防ぐ）。"""
    for exception_type in (CloseConfirmationRequiredError, InvalidStateTransitionError):
        assert issubclass(exception_type, DomainError)
        assert exception_type in _STATUS_AND_CODE


#: フロントだけで発生し、バックエンドが返さないコード（通信失敗・未登録コードの既定文言）。
_FRONTEND_ONLY_ERROR_KEYS = {"NETWORK_ERROR", "default"}


def _load_frontend_error_messages() -> dict[str, str]:
    """`errors.*`直下の文字列値のみを返す（コード→文言の対応表）。`errors.reasons`は
    reason→文言の別の対応表（`_load_frontend_error_reason_messages`）であり、入れ子の
    オブジェクトのため、コード一覧と誤って比較されないようここで除外する。"""
    locale_path = Path(__file__).resolve().parents[2] / "frontend" / "src" / "locales" / "ja.json"
    errors = json.loads(locale_path.read_text(encoding="utf-8"))["errors"]
    return {key: value for key, value in errors.items() if isinstance(value, str)}


def test_every_error_code_has_a_frontend_message():
    """バックエンドが返す全コードに画面文言があること（横断チェック）。

    文言が無いコードは ApiError.localizedMessage が既定文言（errors.default）へ黙って
    落ちるため、利用者には「エラーが発生しました」としか出ず、実行時例外にも型エラーにも
    ならない。実際に RESOURCE_ALLOCATION_REQUIRED が旧名 RESOURCE_RATIO_REQUIRED のまま
    取り残され、既定文言に落ちていた（2026-09-11に修正）。
    """
    messages = _load_frontend_error_messages()
    missing = sorted({code for _, code in _STATUS_AND_CODE.values()} - set(messages))
    assert missing == [], f"ja.json の errors.* に文言が無いエラーコード: {missing}"


def test_frontend_has_no_stale_error_message():
    """使われないコードの文言が残っていないこと（旧名の取り残しを検知する）。"""
    messages = _load_frontend_error_messages()
    backend_codes = {code for _, code in _STATUS_AND_CODE.values()}
    stale = sorted(set(messages) - backend_codes - _FRONTEND_ONLY_ERROR_KEYS)
    assert stale == [], f"バックエンドが返さない文言が残っている: {stale}"


def _domain_error_reasons() -> set[str]:
    """`DomainError`のサブクラスが持つ`reason`クラス属性を全て集める（削除不可エラー3種、
    2026-09-19）。コードは増やさずdetailsのreasonで原因を伝える方式（app/api/errors.py
    handle_domain_error）のため、`_STATUS_AND_CODE`と違って一覧を持つ辞書が存在しない。
    継承ではなく`vars(cls)`で直接定義された属性のみを見るのは、将来reasonを持つ基底クラスが
    増えても、サブクラスの`"reason" in vars(cls)`だけを見れば個々の値を拾えるようにするため。
    """
    reasons: set[str] = set()
    for _, obj in inspect.getmembers(exceptions_module, inspect.isclass):
        if issubclass(obj, DomainError) and "reason" in vars(obj):
            reasons.add(obj.reason)
    return reasons


def _load_frontend_error_reason_messages() -> dict[str, str]:
    locale_path = Path(__file__).resolve().parents[2] / "frontend" / "src" / "locales" / "ja.json"
    return json.loads(locale_path.read_text(encoding="utf-8"))["errors"]["reasons"]


def test_every_domain_error_reason_has_a_frontend_message():
    """削除不可エラーのreasonに画面文言があること（test_every_error_code_has_a_frontend_message
    のreason版、横断チェック）。文言が無いreasonはApiError.localizedMessageが親のcodeの
    汎用文言（VALIDATION_ERROR＝「入力内容に誤りがあります」）へ黙って落ち、削除できない
    理由（実績が残っている等）が利用者に伝わらない。"""
    messages = _load_frontend_error_reason_messages()
    missing = sorted(_domain_error_reasons() - set(messages))
    assert missing == [], f"ja.json の errors.reasons.* に文言が無いreason: {missing}"


def test_frontend_has_no_stale_error_reason_message():
    """使われないreasonの文言が残っていないこと（旧名の取り残しを検知する）。"""
    messages = _load_frontend_error_reason_messages()
    stale = sorted(set(messages) - _domain_error_reasons())
    assert stale == [], f"バックエンドが返さないreasonの文言が残っている: {stale}"


def test_domain_error_is_logged_as_a_warning(client, caplog):
    """業務エラーがログに残ること（Phase40 診断ログ出力・トレース強化）。

    これが無いと、利用者が実際につまずくエラー（400/404/409）の大半がログから
    一切追えない（未分類の500系例外のみが_logger.exceptionで記録されていた）。
    """
    with caplog.at_level(logging.WARNING, logger="app.api.errors"):
        response = client.get("/api/v1/goals/9999")

    assert response.status_code == 404
    messages = [r.getMessage() for r in caplog.records if r.name == "app.api.errors"]
    assert any("NOT_FOUND" in message for message in messages)


def test_request_validation_error_is_logged_without_the_raw_input_value(client, caplog):
    """検証エラーもログに残るが、pydanticのerrors()が持つ`input`（利用者の入力値）は
    絶対に含めないこと（Phase40、ログに入力値を残さない方針）。"""
    secret_looking_value = "利用者だけが知っている秘密の値"
    with caplog.at_level(logging.WARNING, logger="app.api.errors"):
        response = client.post("/api/v1/goals", json={"category": secret_looking_value})

    assert response.status_code == 400
    messages = [r.getMessage() for r in caplog.records if r.name == "app.api.errors"]
    assert any("入力検証エラー" in message for message in messages)
    assert not any(secret_looking_value in message for message in messages)


def test_unexpected_exception_returns_internal_error_body(client, monkeypatch):
    def _boom(_session):
        raise RuntimeError("想定外の内部エラー（テスト用）")

    monkeypatch.setattr(ai_auth, "get_status", _boom)

    with TestClient(app, raise_server_exceptions=False) as non_raising_client:
        response = non_raising_client.get("/api/v1/ai/status")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "予期しないエラーが発生しました",
            "details": [],
        }
    }
