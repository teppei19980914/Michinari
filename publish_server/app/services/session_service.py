"""ブラウザセッション（publish_session）のサービス層（D-18）。

セッショントークンはCookieに平文を格納し、DB側にはSHA-256ハッシュのみを保存する
（`publish_session.id`がハッシュ値そのもの、データモデル3章）。CSRFトークンは
ログイン応答で一度だけ平文を返し、以後は状態変更リクエストの`X-CSRF-Token`ヘッダと
DB保存値を照合する（Cookieには入れない。double-submit cookie方式ではなく、
サーバ側で保持する値とヘッダを比較する方式のため、CSRFトークン自体の読み取り専用Cookieも
不要）。
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants.security import CSRF_TOKEN_BYTES, SESSION_TOKEN_BYTES
from app.models.account import PublishAccount
from app.models.base import utcnow
from app.models.session import PublishSession
from app.services.exceptions import SessionRequiredError


@dataclass(frozen=True)
class IssuedSession:
    raw_token: str
    csrf_token: str
    expires_at: datetime


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_session(db: Session, account: PublishAccount) -> IssuedSession:
    settings = get_settings()
    raw_token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    csrf_token = secrets.token_urlsafe(CSRF_TOKEN_BYTES)
    expires_at = utcnow() + timedelta(hours=settings.session_lifetime_hours)

    db.add(
        PublishSession(
            id=_hash_token(raw_token),
            account_id=account.id,
            csrf_token=csrf_token,
            expires_at=expires_at,
        )
    )
    db.commit()
    return IssuedSession(raw_token=raw_token, csrf_token=csrf_token, expires_at=expires_at)


def get_valid_session(db: Session, raw_token: str) -> PublishSession:
    """有効なセッションを取得する。無い・期限切れの場合は`SessionRequiredError`を送出する。"""
    row = db.get(PublishSession, _hash_token(raw_token))
    if row is None or row.expires_at <= utcnow():
        raise SessionRequiredError()
    row.last_seen_at = utcnow()
    db.commit()
    return row


def delete_session(db: Session, raw_token: str) -> None:
    """ログアウト。存在しない・既に失効済みのトークンに対しても冪等に成功する。"""
    row = db.get(PublishSession, _hash_token(raw_token))
    if row is not None:
        db.delete(row)
        db.commit()
