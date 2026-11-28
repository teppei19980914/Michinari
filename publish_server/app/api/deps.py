"""APIルーター共通の依存関係（DB接続・セッション認証・CSRF検証）。"""

import secrets
from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.constants.security import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from app.database import SessionLocal
from app.models.account import PublishAccount
from app.models.session import PublishSession
from app.services import session_service
from app.services.exceptions import CsrfTokenInvalidError, SessionRequiredError


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_session(request: Request, db: Session = Depends(get_db)) -> PublishSession:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        raise SessionRequiredError()
    return session_service.get_valid_session(db, raw_token)


def get_current_account(
    session: PublishSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> PublishAccount:
    account = db.get(PublishAccount, session.account_id)
    if account is None:  # pragma: no cover (account削除時はCASCADEでsessionも消えるため到達しない)
        raise SessionRequiredError()
    return account


def require_csrf(request: Request, session: PublishSession = Depends(get_current_session)) -> None:
    """状態変更リクエストに必須のCSRFトークン検証（D-18）。`get_current_account`と併用する。

    比較には`secrets.compare_digest`（定数時間比較）を使う。通常の`!=`はPython実装上、
    先頭からの不一致位置によって比較時間が変わり得るため（Python公式`secrets`モジュールの
    ドキュメントが推奨、タイミング攻撃対策、auth-reviewer/secret-reviewerレビュー
    2026-11-28指摘）。
    """
    header_value = request.headers.get(CSRF_HEADER_NAME)
    if not header_value or not secrets.compare_digest(header_value, session.csrf_token):
        raise CsrfTokenInvalidError()
