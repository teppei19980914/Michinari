"""認証API（アカウント作成・ログイン・ログアウト・APIトークン発行/一覧/失効）。

データ構造編6.1相当のベースパス（`/api/v1`）は`main.py`でルーター登録時に付与する。
"""

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_current_account, get_current_session, get_db, require_csrf
from app.config import get_settings
from app.constants.security import SESSION_COOKIE_NAME
from app.models.account import PublishAccount
from app.models.session import PublishSession
from app.schemas.auth import (
    AccountCreateRequest,
    AccountResponse,
    ApiTokenCreateResponse,
    ApiTokenResponse,
    LoginRequest,
    LoginResponse,
)
from app.services import account_service, session_service, token_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
        max_age=settings.session_lifetime_hours * 3600,
    )


@router.post("/account", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(body: AccountCreateRequest, db=Depends(get_db)) -> PublishAccount:
    return account_service.create_account(db, body.username, body.password)


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response, db=Depends(get_db)) -> LoginResponse:
    account = account_service.authenticate(db, body.username, body.password)
    issued = session_service.create_session(db, account)
    _set_session_cookie(response, issued.raw_token)
    return LoginResponse(account=account, csrf_token=issued.csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    request_session: PublishSession = Depends(get_current_session),
    _csrf: None = Depends(require_csrf),
    db=Depends(get_db),
) -> None:
    # Cookie値（平文）はdepsで既にRequestから取得済みだが、削除には元のraw_tokenは不要で
    # ハッシュ済みPK（request_session.id）が分かれば十分なため、session_serviceを経由せず
    # 直接削除する（get_valid_sessionの再ハッシュ計算を避けるため）。
    db.delete(request_session)
    db.commit()
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


@router.post("/tokens", response_model=ApiTokenCreateResponse, status_code=status.HTTP_201_CREATED)
def issue_token(
    account: PublishAccount = Depends(get_current_account),
    _csrf: None = Depends(require_csrf),
    db=Depends(get_db),
) -> ApiTokenCreateResponse:
    raw_token, token = token_service.issue_token(db, account)
    return ApiTokenCreateResponse(id=token.id, token=raw_token, created_at=token.created_at)


@router.get("/tokens", response_model=list[ApiTokenResponse])
def list_tokens(account: PublishAccount = Depends(get_current_account), db=Depends(get_db)) -> list:
    return token_service.list_tokens(db, account)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(
    token_id: int,
    account: PublishAccount = Depends(get_current_account),
    _csrf: None = Depends(require_csrf),
    db=Depends(get_db),
) -> None:
    token_service.revoke_token(db, account, token_id)
