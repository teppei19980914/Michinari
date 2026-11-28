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
from app.models.base import utcnow
from app.services.exceptions import (
    AccountLockedError,
    InvalidCredentialsError,
    UsernameAlreadyExistsError,
    ValidationError,
)

_ph = PasswordHasher()

#: ユーザー名不存在時でも検証時間を一定に保つためのダミーハッシュ（タイミング攻撃対策、
#: STRIDE分析5章「ユーザー名列挙攻撃」）。プロセス起動時に一度だけ生成する。
_DUMMY_PASSWORD_HASH = _ph.hash(secrets.token_urlsafe(32))


def _normalize_password(password: str) -> str:
    """Unicode正規化（NFC）。同じパスワードの異なる正規化形式を同一視する
    （開発Todo_Web公開_v1.0 単位1テスト観点「Unicode正規化」）。"""
    return unicodedata.normalize("NFC", password)


def validate_username(username: str) -> None:
    if not (USERNAME_MIN_LENGTH <= len(username) <= USERNAME_MAX_LENGTH):
        raise ValidationError(
            f"Username must be between {USERNAME_MIN_LENGTH} and {USERNAME_MAX_LENGTH} characters"
        )
    if not USERNAME_PATTERN.match(username):
        raise ValidationError(
            "Username may only contain ASCII letters, digits, underscore, hyphen, and dot"
        )


def validate_password(password: str) -> None:
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
    password_hash = _ph.hash(_normalize_password(password))

    existing = db.query(PublishAccount).filter(PublishAccount.username == username).first()
    if existing is not None:
        raise UsernameAlreadyExistsError()

    account = PublishAccount(username=username, password_hash=password_hash)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _is_locked(account: PublishAccount) -> bool:
    return account.locked_until is not None and account.locked_until > utcnow()


def _record_failed_attempt(db: Session, account: PublishAccount) -> None:
    settings = get_settings()
    account.failed_login_count += 1
    if account.failed_login_count >= settings.login_max_attempts:
        account.locked_until = utcnow() + timedelta(minutes=settings.login_lockout_minutes)
    db.commit()


def _record_successful_login(db: Session, account: PublishAccount, password: str) -> None:
    account.failed_login_count = 0
    account.locked_until = None
    if _ph.check_needs_rehash(account.password_hash):
        account.password_hash = _ph.hash(_normalize_password(password))
    db.commit()


def authenticate(db: Session, username: str, password: str) -> PublishAccount:
    """ユーザー名・パスワードを検証する（D-17）。

    ユーザー名不存在・パスワード不一致のいずれでも同じ`InvalidCredentialsError`を送出する
    （STRIDE分析5章「ログイン」I:情報漏洩対策「エラーメッセージからユーザー存在有無が
    判別可能」）。
    """
    normalized_password = _normalize_password(password)
    account = db.query(PublishAccount).filter(PublishAccount.username == username).first()
    if account is None:
        # タイミング攻撃対策（上記DUMMY_PASSWORD_HASH参照）。結果は使わず時間だけ揃える。
        try:
            _ph.verify(_DUMMY_PASSWORD_HASH, normalized_password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            pass
        raise InvalidCredentialsError()

    if _is_locked(account):
        raise AccountLockedError(account.locked_until)

    try:
        _ph.verify(account.password_hash, normalized_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        _record_failed_attempt(db, account)
        raise InvalidCredentialsError() from None

    _record_successful_login(db, account, password)
    return account
