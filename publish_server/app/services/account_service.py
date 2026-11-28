"""公開アカウント（publish_account）のサービス層。アカウント作成・ログイン認証（D-16・D-17）。

パスワードハッシュ化はargon2-cffi公式ドキュメントで確認済みのAPIを使う
（https://argon2-cffi.readthedocs.io/en/stable/api.html
https://argon2-cffi.readthedocs.io/en/stable/howto.html 、2026-11-28確認、バージョン25.1.0）。
`argon2.PasswordHasher()`は既定でArgon2id（`Type.ID`）、RFC 9106 low-memoryパラメータ
（time_cost=3, memory_cost=65536KiB, parallelism=4）を使う。これらはargon2-cffiの推奨既定値
であり、本サービスでも変更せずそのまま使う（D-17根拠）。
"""

import secrets
import unicodedata
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants.validation import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
    USERNAME_PATTERN,
)
from app.models.account import PublishAccount
from app.models.base import ensure_utc, utcnow
from app.services.exceptions import (
    InvalidCredentialsError,
    UsernameAlreadyExistsError,
    ValidationError,
)

_password_hasher = PasswordHasher()

#: ユーザー名不存在時・ロック中でも検証時間を一定に保つためのダミーハッシュ（タイミング攻撃
#: 対策、STRIDE分析5章「ユーザー名列挙攻撃」）。プロセス起動時に一度だけ生成する。
_DUMMY_PASSWORD_HASH = _password_hasher.hash(secrets.token_urlsafe(32))


def _normalize_password(password: str) -> str:
    """Unicode正規化（NFC）。同じパスワードの異なる正規化形式を同一視する
    （開発Todo_Web公開_v1.0 単位1テスト観点「Unicode正規化」）。"""
    return unicodedata.normalize("NFC", password)


def _dummy_verify(normalized_password: str) -> None:
    """実在のパスワードハッシュと同じコストでダミー検証する（結果は使わず時間だけ揃える）。

    「ユーザー名が存在しない」場合と「ロック中」の場合の両方から呼ぶことで、実際の
    パスワード検証（argon2 verify）を行わない経路でも、行う経路と処理時間を近づける。
    """
    try:
        _password_hasher.verify(_DUMMY_PASSWORD_HASH, normalized_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        pass


def validate_username(username: str) -> None:
    """ユーザー名の文字数・使用可能文字を検証する。違反時は`ValidationError`を送出する。

    許可文字をASCIIのみに制限するのは、Unicode正規化の違いで見た目が同じ別アカウントが
    作られる・既存アカウントにすり替わるリスクをそもそも生じさせないための設計
    （`app/constants/validation.py`のUSERNAME_PATTERN参照）。
    """
    if not (USERNAME_MIN_LENGTH <= len(username) <= USERNAME_MAX_LENGTH):
        raise ValidationError(
            f"Username must be between {USERNAME_MIN_LENGTH} and {USERNAME_MAX_LENGTH} characters"
        )
    if not USERNAME_PATTERN.match(username):
        raise ValidationError(
            "Username may only contain ASCII letters, digits, underscore, hyphen, and dot"
        )


def validate_password(password: str) -> None:
    """パスワードの文字数を検証する。違反時は`ValidationError`を送出する。

    上限はargon2ハッシュ化コスト（既定パラメータでも入力長に比例して処理時間が伸びる）を
    利用したDoSを防ぐための上限。
    """
    if not (PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH):
        raise ValidationError(
            f"Password must be between {PASSWORD_MIN_LENGTH} and {PASSWORD_MAX_LENGTH} characters"
        )


def create_account(db: Session, username: str, password: str) -> PublishAccount:
    """アカウントを作成する（D-16：1利用者1アカウント）。

    ユーザー名の重複有無に関わらずパスワードのハッシュ化を先に行う。重複チェックのみ先に
    行うと、ハッシュ化（約40〜50ms）の有無で応答時間差が生まれ、ユーザー名列挙攻撃に使われる
    （STRIDE分析5章「アカウント作成」S:なりすまし 対策）。
    """
    validate_username(username)
    validate_password(password)
    password_hash = _password_hasher.hash(_normalize_password(password))

    existing = db.query(PublishAccount).filter(PublishAccount.username == username).first()
    if existing is not None:
        raise UsernameAlreadyExistsError()

    account = PublishAccount(username=username, password_hash=password_hash)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _release_expired_lock(db: Session, account: PublishAccount) -> bool:
    """ロック期間が過ぎていれば、失敗カウンタも一緒に解除する。ロック中かどうかを返す。

    カウンタをロック解除時点でリセットしないと、ロックが解けた直後に1回だけ失敗を送るだけで
    即座に再ロックされてしまい、本人が正しいパスワードでログインできる隙を与えずに対象
    アカウントを恒久的にロックし続けられる（低コストの永続DoS、auth-reviewerレビュー
    2026-11-28指摘）。
    """
    if account.locked_until is None:
        return False
    if ensure_utc(account.locked_until) > utcnow():
        return True
    account.failed_login_count = 0
    account.locked_until = None
    db.commit()
    return False


def _record_failed_attempt(db: Session, account: PublishAccount) -> None:
    settings = get_settings()
    account.failed_login_count += 1
    if account.failed_login_count >= settings.login_max_attempts:
        account.locked_until = utcnow() + timedelta(minutes=settings.login_lockout_minutes)
    db.commit()


def _record_successful_login(db: Session, account: PublishAccount, password: str) -> None:
    account.failed_login_count = 0
    account.locked_until = None
    if _password_hasher.check_needs_rehash(account.password_hash):
        account.password_hash = _password_hasher.hash(_normalize_password(password))
    db.commit()


def authenticate(db: Session, username: str, password: str) -> PublishAccount:
    """ユーザー名・パスワードを検証する（D-17）。

    ユーザー名不存在・パスワード不一致・ロック中のいずれでも同じ`InvalidCredentialsError`
    （同一のHTTPステータス・コード・おおむね同じ処理時間）を送出する。ロック中だけ別の
    応答（当初は423 ACCOUNT_LOCKED）を返すと、総当たりで対象ユーザー名の存在有無が
    判別できてしまう（STRIDE分析5章「ログイン」I:情報漏洩対策「エラーメッセージから
    ユーザー存在有無が判別可能」。auth-reviewerレビュー2026-11-28でCRITICAL指摘として
    発見、423を廃止して本対応に変更）。ロック自体はDB側（`failed_login_count`・
    `locked_until`）で継続して機能し、ロック中は正しいパスワードでも必ず失敗する。
    """
    normalized_password = _normalize_password(password)
    account = db.query(PublishAccount).filter(PublishAccount.username == username).first()
    if account is None:
        _dummy_verify(normalized_password)
        raise InvalidCredentialsError()

    if _release_expired_lock(db, account):
        _dummy_verify(normalized_password)
        raise InvalidCredentialsError()

    try:
        _password_hasher.verify(account.password_hash, normalized_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        _record_failed_attempt(db, account)
        raise InvalidCredentialsError() from None

    _record_successful_login(db, account, password)
    return account
