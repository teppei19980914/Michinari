"""フロントエンドのエラー報告API（Phase40 診断ログ出力・トレース強化）。

Reactの`ErrorBoundary`は描画中の例外しか捕捉できず、イベントハンドラ・非同期処理内の
例外やPromiseの未処理rejectionは構造的に取りこぼす。バックエンドの相関ID付きログと
同じファイルへ一本化しないと、フロント側だけで起きた不具合が事後に一切追えないため、
このエンドポイントで受け取ってログへ書き込む。

DBを扱わずログ出力のみのため、サービス層を設けずAPI層に直接実装する（ロジックが薄く、
分割の実益が無いため。CLAUDE.md「サービス層でのHTTP例外の送出」禁止は、ここでは
そもそも例外を送出する分岐がpydantic検証以外に無いため関係しない）。
"""

import logging

from fastapi import APIRouter, status

from app.schemas.client_logs import ClientLogRequest

router = APIRouter(tags=["client-logs"])

_logger = logging.getLogger("app.client")


def _sanitize_single_line(text: str) -> str:
    """改行をエスケープし、1行のログとして扱えるようにする。

    フロントから届く`message`をそのまま改行付きで書き込むと、あたかも別の時刻・レベルの
    ログ行が新たに始まったかのような偽装行を混入させられる（ログインジェクション対策、
    脅威モデルT）。多行が前提の`stack`/`component_stack`はここでは対象にしない
    （明示的な区切りの下に別途書き込むため、境界の誤認は起きない）。
    """
    return text.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


@router.post("/client-logs", status_code=status.HTTP_204_NO_CONTENT)
def report_client_log(payload: ClientLogRequest) -> None:
    """`POST /api/v1/client-logs`: フロントで捕捉した未処理エラーを診断ログへ記録する。"""
    _logger.warning(
        "フロントエンドエラー: path=%s message=%s",
        payload.path,
        _sanitize_single_line(payload.message),
    )
    if payload.stack:
        _logger.warning("stack:\n%s", payload.stack)
    if payload.component_stack:
        _logger.warning("componentStack:\n%s", payload.component_stack)
