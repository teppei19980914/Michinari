"""ドメイン例外→HTTPレスポンスへの変換（データ構造編6.1・6.3）。

サービス層はHTTPExceptionを送出しない（CLAUDE.md「サービス層でのHTTP例外の送出」禁止）。
ここで一元的にドメイン例外を `{"error": {"code": ..., "message": ..., "details": [...]}}`
形式（データ構造編6.1）へ変換する。
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.ai.exceptions import AiAuthRequiredError, AiConfigError, AiError, AiTimeoutError
from app.services.exceptions import (
    AppSettingNotFoundError,
    BackdateLimitExceededError,
    BookAlreadyExistsError,
    ConsentRequiredError,
    CurrentPageExceedsTotalPagesError,
    DomainError,
    ExamResultsIncompleteError,
    ExamSubjectRequiredError,
    ImmutableRecordError,
    InvalidStateTransitionError,
    MaterialHasStudyLogsError,
    MaterialRequiredError,
    NotFoundError,
    PlannedCyclesBelowCompletedError,
    RecapBodyRejectedError,
    RecapPromptTooLongError,
    RecapThemeNameConflictError,
    ResourceAllocationExceededError,
    ResourceAllocationRequiredError,
    ValidationError,
    WorkAssignmentAlreadyExistsError,
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
    BookAlreadyExistsError: (status.HTTP_400_BAD_REQUEST, "BOOK_ALREADY_EXISTS"),
    CurrentPageExceedsTotalPagesError: (
        status.HTTP_400_BAD_REQUEST,
        "CURRENT_PAGE_EXCEEDS_TOTAL_PAGES",
    ),
    WorkAssignmentAlreadyExistsError: (
        status.HTTP_400_BAD_REQUEST,
        "WORK_ASSIGNMENT_ALREADY_EXISTS",
    ),
    ConsentRequiredError: (status.HTTP_400_BAD_REQUEST, "CONSENT_REQUIRED"),
    WorkMemberHasEvaluationReportsError: (status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR"),
    BackdateLimitExceededError: (status.HTTP_400_BAD_REQUEST, "BACKDATE_LIMIT_EXCEEDED"),
    InvalidStateTransitionError: (status.HTTP_409_CONFLICT, "INVALID_STATE_TRANSITION"),
    # 状態エラーではなく「確認待ち」（理由はexceptions.pyの同クラスのdocstring参照）。
    ExamResultsIncompleteError: (status.HTTP_409_CONFLICT, "EXAM_RESULTS_INCOMPLETE"),
    ImmutableRecordError: (status.HTTP_409_CONFLICT, "IMMUTABLE_RECORD"),
    RecapThemeNameConflictError: (status.HTTP_409_CONFLICT, "RECAP_THEME_NAME_CONFLICT"),
    RecapBodyRejectedError: (status.HTTP_409_CONFLICT, "RECAP_BODY_REJECTED"),
    RecapPromptTooLongError: (status.HTTP_409_CONFLICT, "RECAP_PROMPT_TOO_LONG"),
    NotFoundError: (status.HTTP_404_NOT_FOUND, "NOT_FOUND"),
    AppSettingNotFoundError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR"),
    # AI連携（ロジック・プロンプト編16.6の対応表）。
    AiAuthRequiredError: (status.HTTP_401_UNAUTHORIZED, "AI_AUTH_REQUIRED"),
    AiConfigError: (status.HTTP_400_BAD_REQUEST, "AI_CONFIG_ERROR"),
    AiTimeoutError: (status.HTTP_504_GATEWAY_TIMEOUT, "AI_TIMEOUT"),
    AiError: (status.HTTP_502_BAD_GATEWAY, "AI_ERROR"),
}
_FALLBACK = (status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR")

#: SQLiteの書き込みロック待ちタイムアウト（sqlite3.OperationalErrorのメッセージに含まれる文字列）。
_DATABASE_LOCKED_MARKER = "database is locked"
#: DBが他の処理に使用中の場合の（ステータス, コード）。再試行で解消しうるため503とする。
_DATABASE_BUSY = (status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_BUSY")
_DATABASE_BUSY_MESSAGE = "Database is busy with another operation"

_logger = logging.getLogger(__name__)


def _error_body(code: str, message: str, details: list | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


def _internal_error_response() -> JSONResponse:
    """想定外の内部エラーの応答（未分類の例外・想定外のDB例外で共用する、CLAUDE.md DRYの原則）。"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("INTERNAL_ERROR", "An unexpected error occurred"),
    )


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
        # 業務エラーはこれまで一切ログに残らず、利用者が実際につまずくエラーの大半が
        # 事後にトレースできなかった（Phase40）。メッセージはexceptions.pyの全サブクラスで
        # ID・件数・固定文言のみで構成され自由入力文字列を含まないため、そのままログしてよい。
        _logger.warning("業務エラー: code=%s status=%s message=%s", code, status_code, str(exc))
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
        # ログには`loc`/`type`のみを残し、pydanticのerrors()が持つ`input`（利用者の入力値
        # そのもの）は絶対に含めない（Phase40、ログへ入力値を残さない方針）。
        _logger.warning(
            "入力検証エラー: status=400 fields=%s",
            [{"loc": d["loc"], "type": d["type"]} for d in details],
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_error_body("VALIDATION_ERROR", "Invalid input", details),
        )

    @app.exception_handler(OperationalError)
    async def handle_database_operational_error(
        _request: Request, exc: OperationalError
    ) -> JSONResponse:
        """DBの書き込みロック待ちタイムアウト（SQLite「database is locked」）を専用コードで返す。

        AI生成や起動時の自動処理が書き込みロックを握っている間に保存すると発生する。想定外の
        バグと区別し、利用者には「少し待って再試行する」案内を出せるようにする（2026-10-04の
        障害で、汎用の「予期しないエラー」表示では原因も対処も伝わらなかった）。
        それ以外のDB例外は従来どおりINTERNAL_ERRORとして扱う。
        """
        if _DATABASE_LOCKED_MARKER not in str(exc.orig):
            _logger.exception("未分類のデータベース例外を捕捉しました")
            return _internal_error_response()
        _logger.warning(
            "データベースが他の処理に使用中のため応答できませんでした（書き込みロック待ち）"
        )
        status_code, code = _DATABASE_BUSY
        return JSONResponse(
            status_code=status_code, content=_error_body(code, _DATABASE_BUSY_MESSAGE)
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
        return _internal_error_response()
