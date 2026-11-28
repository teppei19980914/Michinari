"""公開APIトークン（publish_api_token）のサービス層。発行・失効・ハッシュ検証（D-19）。

平文トークンは発行時のみ呼び出し元へ返し、DBへは保存しない（保存は`token_hash`
＝SHA-256ハッシュのみ）。`verify_token`は単位2（公開API・閲覧/回答API）のアップロード
エンドポイントが認証に使う想定だが、ハッシュ検証自体は単位1の完了条件（開発Todo_Web公開_v1.0
単位1 変更ファイル一覧「token_service.py（発行・失効・ハッシュ検証）」）に含まれるため、
ここで実装する（単位2側のAPI連携自体は単位1では行わない＝単位2以降の先取り実装はしない）。
"""

import hashlib
import secrets

from sqlalchemy.orm import Session

from app.constants.security import API_TOKEN_BYTES
from app.models.account import PublishAccount
from app.models.base import utcnow
from app.models.token import PublishApiToken
from app.services.exceptions import TokenNotFoundError


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_token(db: Session, account: PublishAccount) -> tuple[str, PublishApiToken]:
    """新しいAPIトークンを発行する。戻り値の平文トークンは呼び出し元がこの時点でのみ扱える。"""
    raw_token = secrets.token_urlsafe(API_TOKEN_BYTES)
    token = PublishApiToken(account_id=account.id, token_hash=_hash_token(raw_token))
    db.add(token)
    db.commit()
    db.refresh(token)
    return raw_token, token


def list_tokens(db: Session, account: PublishAccount) -> list[PublishApiToken]:
    """アカウントが持つトークンのメタデータ一覧（平文は返さない。作成日時の降順）。"""
    return (
        db.query(PublishApiToken)
        .filter(PublishApiToken.account_id == account.id)
        .order_by(PublishApiToken.created_at.desc(), PublishApiToken.id.desc())
        .all()
    )


def revoke_token(db: Session, account: PublishAccount, token_id: int) -> None:
    """トークンを失効させる（D-21：ログイン中のアカウント自身のトークンのみ操作可能）。"""
    token = (
        db.query(PublishApiToken)
        .filter(PublishApiToken.id == token_id, PublishApiToken.account_id == account.id)
        .first()
    )
    if token is None:
        raise TokenNotFoundError(token_id)
    if token.revoked_at is None:
        token.revoked_at = utcnow()
        db.commit()


def verify_token(db: Session, raw_token: str) -> PublishAccount | None:
    """トークンを検証し、有効であれば紐づくアカウントを返す。無効・失効済みならNoneを返す。

    呼び出し元（単位2のアップロードAPI）がNone時に適切なドメイン例外へ変換する
    （本モジュールはAPI層の事情を知らないため、ここでは例外を送出しない）。
    """
    token = (
        db.query(PublishApiToken)
        .filter(PublishApiToken.token_hash == _hash_token(raw_token))
        .first()
    )
    if token is None or token.revoked_at is not None:
        return None
    token.last_used_at = utcnow()
    db.commit()
    account = db.get(PublishAccount, token.account_id)
    return account
