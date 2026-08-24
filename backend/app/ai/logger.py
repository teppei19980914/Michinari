"""通信ログ（設計書 ロジック・プロンプト編16.8、データ構造編5.5 ai_log）。

送信文字数・縮退有無を記録し、入力上限の実測値の把握に用いる。log.ai_enabled が
無効な場合は記録しない。保持期間（log.retention_days）を超過したレコードは
起動時に削除する。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import LOG_AI_ENABLED, LOG_RETENTION_DAYS
from app.constants.enums import AiPurpose
from app.models.ai import AiLog
from app.services import setting_reader


def record_call(
    session: Session,
    *,
    purpose: AiPurpose,
    conversation_uid: str | None,
    request_body: str,
    response_body: str | None,
    prompt_chars: int | None,
    was_truncated: bool,
    latency_ms: int | None,
    error_type: str | None,
    error_message: str | None,
) -> None:
    """AI呼び出し1回分をai_logへ記録する（16.8）。"""
    if not setting_reader.get_bool(session, LOG_AI_ENABLED):
        return
    session.add(
        AiLog(
            purpose=purpose,
            conversation_uid=conversation_uid,
            request_body=request_body,
            response_body=response_body,
            prompt_chars=prompt_chars,
            was_truncated=was_truncated,
            latency_ms=latency_ms,
            error_type=error_type,
            error_message=error_message,
        )
    )
    session.flush()


def purge_expired(session: Session, today: dt.date) -> int:
    """保持期間（log.retention_days）を超過したai_logを削除する（データ構造編5.5、起動時実行）。"""
    retention_days = setting_reader.get_int(session, LOG_RETENTION_DAYS)
    cutoff = dt.datetime.combine(
        today - dt.timedelta(days=retention_days), dt.time.min, tzinfo=dt.UTC
    ).replace(tzinfo=None)
    deleted = session.query(AiLog).filter(AiLog.created_at < cutoff).delete()
    session.flush()
    return deleted
