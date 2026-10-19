"""record_service_reading のテスト（設計書データ構造編5.4・6.2、仕様書6.4〜6.7・7.2・14章、
実装フェーズ分割計画書Phase15・S02）。共通処理・カテゴリ横断の相互独立性のテストは
test_record_service_common.pyを参照（実装フェーズ分割計画書S02、test_record_service.py
からの分割）。
"""

import datetime as dt

import pytest

from app.constants.enums import Environment, RecordState
from app.models.record import WeeklySummary
from app.models.resource import ResourceSlot
from app.services import record_service_common, record_service_reading
from app.services.exceptions import (
    CurrentPageExceedsTotalPagesError,
    ImmutableRecordError,
    NotFoundError,
)
from app.services.record_service_reading import ReadingLogItem
from tests import reading_helpers


def _make_slot(session) -> ResourceSlot:
    """時間枠を1件用意する（投下時間は時間枠ごとに入力する仕様、仕様書6.5）。"""
    slot = ResourceSlot(
        name="夜",
        start_time=dt.time(20, 0),
        end_time=dt.time(22, 0),
        environment=Environment.PC,
        display_order=1,
    )
    session.add(slot)
    session.flush()
    return slot


def _make_reading_goal(session):
    return reading_helpers.make_reading_goal(session, name="読書目標")


def _make_book(session, goal, **overrides):
    return reading_helpers.make_book(session, goal.id, **overrides)


def _reading_log(book_id, **overrides):
    return reading_helpers.reading_log_item(book_id, **overrides)


def test_register_progress_creates_reading_log(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
        seeded_session, today, [], today, [_reading_log(book.id)]
    )

    assert len(record.reading_logs) == 1
    assert record.reading_logs[0].recall_body == "今日読んだ内容の想起"


def test_register_progress_rejects_current_page_over_total_pages(seeded_session):
    """現在ページが総ページ数を超える入力は拒否する（進捗率が100%を超えないようにする、
    仕様変更2026-09-11）。汎用のVALIDATION_ERRORではなく専用の例外とし、画面に「総ページ数
    以下で入力してください」と表示できるようにする。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, total_pages=300)
    today = dt.date(2026, 3, 10)

    with pytest.raises(CurrentPageExceedsTotalPagesError):
        record_service_common.register_progress(
            seeded_session, today, [], today, [_reading_log(book.id, current_page=301)]
        )


def test_register_progress_accepts_current_page_equal_to_total_pages(seeded_session):
    """境界値。読了位置ちょうど（＝進捗率100%）は受け付けること。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal, total_pages=300)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
        seeded_session, today, [], today, [_reading_log(book.id, current_page=300)]
    )

    assert record.reading_logs[0].current_page == 300


def test_register_progress_accepts_reading_log_without_current_page(seeded_session):
    """現在ページは任意入力のまま（要件定義書R-65）。未入力でも登録できること。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
        seeded_session, today, [], today, [_reading_log(book.id, current_page=None)]
    )

    assert record.reading_logs[0].current_page is None


def test_register_progress_accepts_reading_only_without_study_logs(seeded_session):
    """資格試験のstudy_logsが空でも、読書のreading_logsのみで登録できる
    （両カテゴリの目標が同時進行しうるため、study_logsを必須にできない）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
        seeded_session, today, [], today, [_reading_log(book.id)]
    )

    assert record.reading_record_state == RecordState.PROGRESS_ONLY
    assert record.exam_record_state is None


def test_register_progress_rejects_unknown_book(seeded_session):
    today = dt.date(2026, 3, 10)

    with pytest.raises(NotFoundError):
        record_service_common.register_progress(
            seeded_session, today, [], today, [_reading_log(9999)]
        )


def test_register_progress_updates_existing_reading_log_for_same_book(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record_service_common.register_progress(
        seeded_session, today, [], today, [_reading_log(book.id)]
    )
    record = record_service_common.register_progress(
        seeded_session,
        today,
        [],
        today,
        [_reading_log(book.id, recall_body="上書き後の想起", current_page=20)],
    )

    assert len(record.reading_logs) == 1
    assert record.reading_logs[0].recall_body == "上書き後の想起"
    assert record.reading_logs[0].current_page == 20


def test_finalize_reading_record_persists_reading_log(seeded_session):
    """読書の確定は/finalize（EXAM）とは独立した専用関数（仕様変更2026-09-05:
    カテゴリごとに独立して確定できるようにするため）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_reading.finalize_reading_record(
        seeded_session, today, [_reading_log(book.id)], today
    )

    assert record.reading_record_state == RecordState.REPORTED
    assert record.exam_record_state is None
    assert len(record.reading_logs) == 1


def test_finalize_reading_record_allows_reading_log_without_diary(seeded_session):
    """想起のみの入力でも確定できる（要件定義書R-65「数値実績の入力を必須としない」）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_reading.finalize_reading_record(
        seeded_session, today, [_reading_log(book.id)], today
    )

    assert record.reading_record_state == RecordState.REPORTED
    assert len(record.reading_logs) == 1


def test_finalize_reading_record_rejects_already_reported(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)
    record_service_reading.finalize_reading_record(
        seeded_session, today, [_reading_log(book.id)], today
    )

    with pytest.raises(ImmutableRecordError):
        record_service_reading.finalize_reading_record(
            seeded_session, today, [_reading_log(book.id)], today
        )


# --- 前回の記録（記録画面改善タスク2026-09-17、get_previous_reading_log） ---


def test_get_previous_reading_log_returns_most_recent_before_target_date(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    record_service_reading.finalize_reading_record(
        seeded_session,
        dt.date(2026, 3, 8),
        [_reading_log(book.id, recall_body="3/8の想起")],
        dt.date(2026, 3, 8),
    )
    record_service_reading.finalize_reading_record(
        seeded_session,
        dt.date(2026, 3, 9),
        [_reading_log(book.id, recall_body="3/9の想起")],
        dt.date(2026, 3, 9),
    )

    entry = record_service_reading.get_previous_reading_log(
        seeded_session, book.id, dt.date(2026, 3, 10)
    )

    assert entry.record_date == dt.date(2026, 3, 9)
    assert entry.body == "3/9の想起"


def test_get_previous_reading_log_returns_none_when_no_record_exists(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)

    entry = record_service_reading.get_previous_reading_log(
        seeded_session, book.id, dt.date(2026, 3, 10)
    )

    assert entry is None


# --- 時間枠別入力の検証（読書分） ---


def test_register_progress_records_reading_slot_minutes(seeded_session):
    """読書記録も時間枠ごとに時間を持ち、合計が minutes_spent になること（R-64・R-71）。"""
    reading_goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, reading_goal)
    slot = _make_slot(seeded_session)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
        seeded_session,
        today,
        [],
        today,
        reading_items=[
            ReadingLogItem(
                book_id=book.id,
                recall_body="想起",
                current_page=None,
                slot_minutes={slot.id: 25},
            )
        ],
    )

    assert record.reading_logs[0].minutes_spent == 25
    assert [(row.slot_id, row.minutes) for row in record.reading_logs[0].slot_times] == [
        (slot.id, 25)
    ]


# --- 週次要約の無効化（G4、開発Todo S06） ---


def test_register_progress_invalidates_existing_weekly_summary_for_edited_week(seeded_session):
    """既に週次要約が生成済みの過去週へ想起記録を追記すると、その週の要約（非匿名化・
    匿名化とも）が削除される（record_service_examと同じ理由の横展開）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    week_start = dt.date(2026, 3, 2)  # 月曜
    edited_date = dt.date(2026, 3, 4)  # 同じ週の水曜
    non_anon = WeeklySummary(
        goal_id=goal.id,
        week_start_date=week_start,
        week_end_date=week_start + dt.timedelta(days=6),
        summary_body="既に生成済み",
    )
    anon = WeeklySummary(
        goal_id=goal.id,
        week_start_date=week_start,
        week_end_date=week_start + dt.timedelta(days=6),
        summary_body="既に生成済み（匿名化版）",
        is_anonymized=True,
    )
    seeded_session.add_all([non_anon, anon])
    seeded_session.flush()

    record_service_common.register_progress(
        seeded_session, edited_date, [], dt.date(2026, 3, 10), [_reading_log(book.id)]
    )

    assert seeded_session.get(WeeklySummary, non_anon.id) is None
    assert seeded_session.get(WeeklySummary, anon.id) is None
