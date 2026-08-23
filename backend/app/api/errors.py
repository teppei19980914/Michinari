"""ドメイン例外→HTTPレスポンスへの変換（データ構造編6.1・6.3）。

サービス層はHTTPExceptionを送出しない（CLAUDE.md「サービス層でのHTTP例外の送出」禁止）。
ここで一元的にドメイン例外を `{"error": {"code": ..., "message": ..., "details": [...]}}`
形式（データ構造編6.1）へ変換する。
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.exceptions import (
    AppSettingNotFoundError,
    DomainError,
    InvalidStateTransitionError,
    MaterialHasStudyLogsError,
    NotFoundError,
    PlannedCyclesBelowCompletedError,
    ResourceRatioExceededError,
    ValidationError,
)

#: ドメイン例外の型 → (HTTPステータス, エラーコード)（データ構造編6.3）。
#: 未登録の DomainError サブクラスは INTERNAL_ERROR として扱う（想定外の内部エラー）。
_STATUS_AND_CODE: dict[type[DomainError], tuple[int, str]] = {
    ValidationError: (status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR"),
    ResourceRatioExceededError: (status.HTTP_400_BAD_REQUEST, "RESOURCE_EXCEEDED"),
    PlannedCyclesBelowCompletedError: (status.HTTP_400_BAD_REQUEST, "CYCLE_CONFLICT"),
    MaterialHasStudyLogsError: (status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR"),
    InvalidStateTransitionError: (status.HTTP_409_CONFLICT, "INVALID_STATE_TRANSITION"),
    NotFoundError: (status.HTTP_404_NOT_FOUND, "NOT_FOUND"),
    AppSettingNotFoundError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR"),
}
_FALLBACK = (status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR")


def _error_body(code: str, message: str, details: list | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


def register_exception_handlers(app: FastAPI) -> None:
    """main.py の create_app から呼び出す（データ構造編6.1の応答形式を全ルーターに適用する）。"""

    @app.exception_handler(DomainError)
    async def handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        status_code, code = _STATUS_AND_CODE.get(type(exc), _FALLBACK)
        return JSONResponse(status_code=status_code, content=_error_body(code, str(exc)))

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
