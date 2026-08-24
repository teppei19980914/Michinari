"""ai/logger のテスト（ロジック・プロンプト編16.8、データ構造編5.5 ai_log）。"""

import datetime as dt

from app.ai import logger as ai_logger
from app.constants.app_setting_keys import LOG_AI_ENABLED
from app.constants.enums import AiPurpose
from app.models.ai import AiLog
from app.models.setting import AppSetting


def _set_setting(session, key, value):
    session.query(AppSetting).filter_by(key=key).update({"value": value})
    session.flush()


def test_record_call_inserts_row_when_log_enabled(seeded_session):
    ai_logger.record_call(
        seeded_session,
        purpose=AiPurpose.DAILY_FEEDBACK,
        conversation_uid="chat-1",
        request_body="送信内容",
        response_body="応答内容",
        prompt_chars=100,
        was_truncated=False,
        latency_ms=500,
        error_type=None,
        error_message=None,
    )

    rows = seeded_session.query(AiLog).all()
    assert len(rows) == 1
    assert rows[0].purpose == AiPurpose.DAILY_FEEDBACK
    assert rows[0].prompt_chars == 100
    assert rows[0].was_truncated is False


def test_record_call_skips_insert_when_log_disabled(seeded_session):
    _set_setting(seeded_session, LOG_AI_ENABLED, "false")

    ai_logger.record_call(
        seeded_session,
        purpose=AiPurpose.DAILY_MESSAGE,
        conversation_uid=None,
        request_body="送信内容",
        response_body=None,
        prompt_chars=10,
        was_truncated=False,
        latency_ms=None,
        error_type="AiError",
        error_message="失敗",
    )

    assert seeded_session.query(AiLog).count() == 0


def test_record_call_records_error_fields(seeded_session):
    ai_logger.record_call(
        seeded_session,
        purpose=AiPurpose.WEEKLY_SUMMARY,
        conversation_uid="chat-2",
        request_body="送信内容",
        response_body=None,
        prompt_chars=200,
        was_truncated=True,
        latency_ms=None,
        error_type="AiTimeoutError",
        error_message="タイムアウトしました",
    )

    row = seeded_session.query(AiLog).one()
    assert row.error_type == "AiTimeoutError"
    assert row.error_message == "タイムアウトしました"
    assert row.was_truncated is True


def test_purge_expired_deletes_only_old_rows(seeded_session):
    old_log = AiLog(
        purpose=AiPurpose.DAILY_FEEDBACK,
        conversation_uid=None,
        request_body="古い",
        response_body=None,
        prompt_chars=None,
        was_truncated=False,
    )
    seeded_session.add(old_log)
    seeded_session.flush()
    # created_atはデフォルトで現在時刻のため、保持期間より前の日時へ直接更新する。
    seeded_session.query(AiLog).filter_by(id=old_log.id).update(
        {"created_at": dt.datetime(2020, 1, 1)}
    )
    recent_log = AiLog(
        purpose=AiPurpose.DAILY_FEEDBACK,
        conversation_uid=None,
        request_body="新しい",
        response_body=None,
        prompt_chars=None,
        was_truncated=False,
    )
    seeded_session.add(recent_log)
    # bulk update/deleteの評価戦略がインメモリのcreated_at属性（tz-aware）とDB上の値
    # （tz-naiveで保存される、app.models.base.utcnow参照）を混在比較しないよう、
    # 一度commitしてセッションをexpireさせてからpurge_expiredを呼ぶ。
    seeded_session.commit()

    deleted = ai_logger.purge_expired(seeded_session, dt.date(2026, 8, 24))

    assert deleted == 1
    remaining = seeded_session.query(AiLog).all()
    assert len(remaining) == 1
    assert remaining[0].request_body == "新しい"
