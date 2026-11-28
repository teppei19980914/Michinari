"""ドメイン例外→HTTPレスポンスへの変換（publish_server独自実装、D-24）。

backend/app/api/errors.pyと同じ設計思想（サービス層はHTTPExceptionを送出しない）だが、
別ディレクトリ配置のため既存モジュールをimportせず、ここで独立に実装する。
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.services.exceptions import (
    CsrfTokenInvalidError,
    DomainError,
    InvalidApiTokenError,
    InvalidCredentialsError,
    QuestionNotFoundError,
    SessionRequiredError,
    SnapshotNotFoundError,
    SnapshotTooLargeError,
    TokenNotFoundError,
    TooManyItemsError,
    UsernameAlreadyExistsError,
    ValidationError,
    VocabDeckNotPublishedError,
)

_STATUS_AND_CODE: dict[type[DomainError], tuple[int, str]] = {
    ValidationError: (status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR"),
    UsernameAlreadyExistsError: (status.HTTP_400_BAD_REQUEST, "USERNAME_ALREADY_EXISTS"),
    InvalidCredentialsError: (status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS"),
    SessionRequiredError: (status.HTTP_401_UNAUTHORIZED, "SESSION_REQUIRED"),
    CsrfTokenInvalidError: (status.HTTP_403_FORBIDDEN, "CSRF_TOKEN_INVALID"),
    TokenNotFoundError: (status.HTTP_404_NOT_FOUND, "NOT_FOUND"),
    InvalidApiTokenError: (status.HTTP_401_UNAUTHORIZED, "API_TOKEN_INVALID"),
    SnapshotTooLargeError: (status.HTTP_400_BAD_REQUEST, "SNAPSHOT_TOO_LARGE"),
    TooManyItemsError: (status.HTTP_400_BAD_REQUEST, "TOO_MANY_ITEMS"),
    VocabDeckNotPublishedError: (status.HTTP_400_BAD_REQUEST, "VOCAB_DECK_NOT_PUBLISHED"),
    SnapshotNotFoundError: (status.HTTP_404_NOT_FOUND, "NOT_FOUND"),
    QuestionNotFoundError: (status.HTTP_404_NOT_FOUND, "NOT_FOUND"),
}
_FALLBACK = (status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR")

_logger = logging.getLogger(__name__)


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    """main.pyのcreate_appから呼び出す。"""

    @app.exception_handler(DomainError)
    async def handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        status_code, code = _STATUS_AND_CODE.get(type(exc), _FALLBACK)
        _logger.warning("業務エラー: code=%s status=%s message=%s", code, status_code, str(exc))
        return JSONResponse(status_code=status_code, content=_error_body(code, str(exc)))

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # ログには`loc`/`type`のみを残し、入力値そのもの（errors()の`input`）は含めない
        # （backend/app/api/errors.pyと同じ方針。パスワード等の機微な入力を残さない）。
        details = [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        _logger.warning("入力検証エラー: status=400 fields=%s", details)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error_body("VALIDATION_ERROR", "Invalid input"),
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
        """DB関連の例外は型名のみをログに残す（secret-reviewerレビュー2026-11-28指摘）。

        本番の`PUBLISH_DATABASE_URL`はSupabaseの認証情報を含む接続文字列であり、DBドライバ
        （psycopg等）の例外メッセージに接続情報が含まれないことを一次ソースで確認できて
        いない。`logger.exception`（`exc_info=True`）はトレースバック内に例外の文字列表現
        （接続情報を含みうる）をそのまま埋め込むため使わず、型名のみを`logger.error`で残す。
        """
        _logger.error("データベース関連の例外を捕捉しました: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("INTERNAL_ERROR", "An unexpected error occurred"),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        """未分類の例外を拾う最終防波堤。スタックトレースはログにのみ残す。"""
        _logger.exception("未分類の例外を捕捉しました")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("INTERNAL_ERROR", "An unexpected error occurred"),
        )
