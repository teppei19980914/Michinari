"""ドメイン例外→HTTPレスポンスへの変換（データ構造編6.1・6.3）。

サービス層はHTTPExceptionを送出しない（CLAUDE.md「サービス層でのHTTP例外の送出」禁止）。
ここで一元的にドメイン例外を `{"error": {"code": ..., "message": ..., "details": [...]}}`
形式（データ構造編6.1）へ変換する。
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.ai.exceptions import AiAuthRequiredError, AiConfigError, AiError, AiTimeoutError
from app.services.exceptions import (
    AppSettingNotFoundError,
    BackdateLimitExceededError,
    BookAlreadyExistsError,
    BookHasReadingLogsError,
    CloseConfirmationRequiredError,
    ConsentRequiredError,
    CurrentPageExceedsTotalPagesError,
    DomainError,
    ExamSubjectRequiredError,
    ImmutableRecordError,
    InvalidStateTransitionError,
    MaterialHasStudyLogsError,
    MaterialRequiredError,
    NotFoundError,
    PlannedCyclesBelowCompletedError,
    ResourceAllocationExceededError,
    ResourceAllocationRequiredError,
    ValidationError,
    WorkAssignmentAlreadyExistsError,
    WorkAssignmentHasWorkLogsError,
    WorkMemberHasEvaluationReportsError,
)

#: ドメイン例外の型 → (HTTPステータス, エラーコード)（データ構造編6.3）。
#: 未登録の DomainError サブクラスは INTERNAL_ERROR として扱う（想定外の内部エラー）。
_STATUS_AND_CODE: dict[type[DomainError], tuple[int, str]] = {
    ValidationError: (status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR"),
    ExamSubjectRequiredError: (status.HTTP_400_BAD_REQUEST, "EXAM_SUBJECT_REQUIRED"),
    MaterialRequiredError: (status.HTTP_400_BAD_REQUEST, "MATERIAL_REQUIRED"),
    ResourceAllocationRequiredError: (
        status.HTTP_400_BAD_REQUEST,
        "RESOURCE_ALLOCATION_REQUIRED",
    ),
    ResourceAllocationExceededError: (status.HTTP_400_BAD_REQUEST, "RESOURCE_EXCEEDED"),
    PlannedCyclesBelowCompletedError: (status.HTTP_400_BAD_REQUEST, "CYCLE_CONFLICT"),
    MaterialHasStudyLogsError: (status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR"),
    BookHasReadingLogsError: (status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR"),
    BookAlreadyExistsError: (status.HTTP_400_BAD_REQUEST, "BOOK_ALREADY_EXISTS"),
    CurrentPageExceedsTotalPagesError: (
        status.HTTP_400_BAD_REQUEST,
        "CURRENT_PAGE_EXCEEDS_TOTAL_PAGES",
    ),
    WorkAssignmentHasWorkLogsError: (status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR"),
    WorkAssignmentAlreadyExistsError: (
        status.HTTP_400_BAD_REQUEST,
        "WORK_ASSIGNMENT_ALREADY_EXISTS",
    ),
    ConsentRequiredError: (status.HTTP_400_BAD_REQUEST, "CONSENT_REQUIRED"),
    WorkMemberHasEvaluationReportsError: (status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR"),
    BackdateLimitExceededError: (status.HTTP_400_BAD_REQUEST, "BACKDATE_LIMIT_EXCEEDED"),
    InvalidStateTransitionError: (status.HTTP_409_CONFLICT, "INVALID_STATE_TRANSITION"),
    # 状態エラーではなく「確認待ち」（理由はexceptions.pyの同クラスのdocstring参照）。
    CloseConfirmationRequiredError: (status.HTTP_409_CONFLICT, "CLOSE_CONFIRMATION_REQUIRED"),
    ImmutableRecordError: (status.HTTP_409_CONFLICT, "IMMUTABLE_RECORD"),
    NotFoundError: (status.HTTP_404_NOT_FOUND, "NOT_FOUND"),
    AppSettingNotFoundError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR"),
    # AI連携（ロジック・プロンプト編16.6の対応表）。
    AiAuthRequiredError: (status.HTTP_401_UNAUTHORIZED, "AI_AUTH_REQUIRED"),
    AiConfigError: (status.HTTP_400_BAD_REQUEST, "AI_CONFIG_ERROR"),
    AiTimeoutError: (status.HTTP_504_GATEWAY_TIMEOUT, "AI_TIMEOUT"),
    AiError: (status.HTTP_502_BAD_GATEWAY, "AI_ERROR"),
}
_FALLBACK = (status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR")

_logger = logging.getLogger(__name__)


def _error_body(code: str, message: str, details: list | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


def register_exception_handlers(app: FastAPI) -> None:
    """main.py の create_app から呼び出す（データ構造編6.1の応答形式を全ルーターに適用する）。"""

    @app.exception_handler(DomainError)
    async def handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        status_code, code = _STATUS_AND_CODE.get(type(exc), _FALLBACK)
        # 一部のドメイン例外はコード自体を増やさず（削除対象に実績が紐づく3種、
        # app/services/exceptions.pyのreasonクラス属性参照）、detailsのreasonで
        # 原因を画面へ伝える（2026-09-19、非エンジニア向けエラー表示改善）。
        reason = getattr(exc, "reason", None)
        details = [{"reason": reason}] if reason else None
        return JSONResponse(status_code=status_code, content=_error_body(code, str(exc), details))

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI既定は422だが、データ構造編6.3のVALIDATION_ERRORは400と定義されているため揃える。
        details = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error_body("VALIDATION_ERROR", "入力値が不正です", details),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        """DomainError/RequestValidationError以外の未分類の例外を拾う最終防波堤。

        これが無いと、想定外の例外（バグ・DB接続断等）がFastAPI既定の応答（本アプリの
        {"error": {"code", ...}}形式ではない）で返り、フロントのエラー解析が破綻して
        利用者に何も表示されない事態になりうる（2026-09-19、非エンジニア向けエラー
        表示改善の一環で発見）。スタックトレースはログにのみ残し、利用者へは返さない。
        """
        _logger.exception("未分類の例外を捕捉しました")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("INTERNAL_ERROR", "予期しないエラーが発生しました"),
        )
