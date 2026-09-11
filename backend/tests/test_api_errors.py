"""ドメイン例外→エラーコードの対応表のテスト（データ構造編6.3、app/api/errors.py）。

コード文字列はバックエンド（_STATUS_AND_CODE）・フロント（constants/errorCodes.ts）・
ロケール（locales/ja.json の errors.*）・設計書6.3の4箇所に手書きで並存する。綴りがずれても
実行時例外にならず（画面は既定文言へ黙って落ちる）型検査でも検知できないため、
ここで値そのものを固定する。
"""

import json
from pathlib import Path

from fastapi import status

from app.api.errors import _STATUS_AND_CODE
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
    locale_path = Path(__file__).resolve().parents[2] / "frontend" / "src" / "locales" / "ja.json"
    return json.loads(locale_path.read_text(encoding="utf-8"))["errors"]


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
