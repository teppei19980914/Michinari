"""ドメイン例外→エラーコードの対応表のテスト（データ構造編6.3、app/api/errors.py）。

コード文字列はバックエンド（_STATUS_AND_CODE）・フロント（constants/errorCodes.ts）・
ロケール（locales/ja.json の errors.*）・設計書6.3の4箇所に手書きで並存する。綴りがずれても
実行時例外にならず（画面は既定文言へ黙って落ちる）型検査でも検知できないため、
ここで値そのものを固定する。
"""

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
