"""ブラウザセッション（publish_session）のサービス層（D-18）。

セッショントークンはCookieに平文を格納し、DB側にはSHA-256ハッシュのみを保存する
（`publish_session.id`がハッシュ値そのもの、データモデル3章）。CSRFトークンは
ログイン応答で一度だけ平文を返し、以後は状態変更リクエストの`X-CSRF-Token`ヘッダと
DB保存値を照合する（Cookieには入れない。double-submit cookie方式ではなく、
サーバ側で保持する値とヘッダを比較する方式のため、CSRFトークン自体の読み取り専用Cookieも
不要）。
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants.security import CSRF_TOKEN_BYTES, SESSION_TOKEN_BYTES
from app.models.account import PublishAccount
from app.models.base import ensure_utc, utcnow
from app.models.session import PublishSession
from app.services.exceptions import SessionRequiredError
from app.services.token_hashing import hash_token


@dataclass(frozen=True)
class IssuedSession:
    raw_token: str
    csrf_token: str
    expires_at: datetime


def create_session(db: Session, account: PublishAccount) -> IssuedSession:
    """ログイン成功時に新規セッションを発行する（常に新しいセッションIDを生成する。

    クライアント指定のセッションIDを引き継ぐ経路は無いため、セッション固定
    （session fixation）攻撃の余地が無い）。

    戻り値の`raw_token`はCookieへ、`csrf_token`はレスポンス本文へ、それぞれ一度だけ
    平文で渡す（以後はDB側のハッシュ・保存値と照合するのみ）。
    """
    settings = get_settings()
    raw_token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    csrf_token = secrets.token_urlsafe(CSRF_TOKEN_BYTES)
    expires_at = utcnow() + timedelta(hours=settings.session_lifetime_hours)

    db.add(
        PublishSession(
            id=hash_token(raw_token),
            account_id=account.id,
            csrf_token=csrf_token,
            expires_at=expires_at,
        )
    )
    db.commit()
    return IssuedSession(raw_token=raw_token, csrf_token=csrf_token, expires_at=expires_at)


def get_valid_session(db: Session, raw_token: str) -> PublishSession:
    """有効なセッションを取得する。無い・期限切れの場合は`SessionRequiredError`を送出する。"""
    row = db.get(PublishSession, hash_token(raw_token))
    if row is None or ensure_utc(row.expires_at) <= utcnow():
        raise SessionRequiredError()
    row.last_seen_at = utcnow()
    db.commit()
    return row


def delete_session(db: Session, raw_token: str) -> None:
    """ログアウト。存在しない・既に失効済みのトークンに対しても冪等に成功する。"""
    row = db.get(PublishSession, hash_token(raw_token))
    if row is not None:
        db.delete(row)
        db.commit()
