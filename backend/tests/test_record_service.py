"""record_service のテスト（設計書データ構造編5.4・6.2、仕様書6.4〜6.7・7.2・14章、
実装フェーズ分割計画書Phase4）。

today はサービス層の引数として明示的に渡す設計のため、システム時刻に依存せず
決定論的にテストできる（呼び出し側=API層がgoal_service.resolve_todayで算出する）。
"""

import datetime as dt

import pytest

from app.constants.enums import GoalCategory, GoalStatus, QualityMetricType, RecordState
from app.models.book import Book
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, RecordComment
from app.models.work import WorkAssignment
from app.services import cycle_service, record_service
from app.services.exceptions import (
    BackdateLimitExceededError,
    ImmutableRecordError,
    NotFoundError,
    ValidationError,
)
from app.services.record_service import DiaryEntryItem, ReadingLogItem, StudyLogItem, WorkLogItem


def _make_goal(session, status=GoalStatus.ACTIVE, name="目標A"):
    goal = Goal(name=name, start_date=dt.date(2026, 1, 1), status=status)
    session.add(goal)
    session.flush()
    return goal


def _make_material(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        name="教材A",
        unit_label="ページ",
        total_amount=100.0,
        planned_cycles=1,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 12, 31),
        due_date_is_manual=True,
        quality_metric_type=QualityMetricType.NONE,
        display_order=1,
    )
    defaults.update(overrides)
    material = Material(**defaults)
    session.add(material)
    session.flush()
    return material


def _log(material_id, **overrides):
    defaults = dict(
        material_id=material_id,
        slot_minutes={},
        amount_completed=10,
        cycle_number=1,
        quality_value=None,
    )
    defaults.update(overrides)
    return StudyLogItem(**defaults)


def _diary(goal_id, diary_body="", diary_learned=""):
    return DiaryEntryItem(goal_id=goal_id, diary_body=diary_body, diary_learned=diary_learned)


# --- register_progress ---


def test_register_progress_creates_record_and_study_log(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service.register_progress(
        seeded_session, today, [_log(material.id, cycle_number=None)], today
    )

    assert record.exam_record_state == RecordState.PROGRESS_ONLY
    assert len(record.study_logs) == 1
    assert record.study_logs[0].cycle_number == 1  # 既定値=算出された現在周回（Phase4完了条件）


def test_register_progress_rejects_future_date(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service.register_progress(
            seeded_session, today + dt.timedelta(days=1), [_log(material.id)], today
        )


def test_register_progress_allows_far_past_date(seeded_session):
    """進捗のみ登録は『当日または前日以前』であり、任意の過去日を許容する（仕様書7.2）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service.register_progress(
        seeded_session, dt.date(2026, 1, 1), [_log(material.id)], today
    )
    assert record.exam_record_state == RecordState.PROGRESS_ONLY


def test_register_progress_rejects_update_to_reported_record(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)
    seeded_session.add(DailyRecord(record_date=today, exam_record_state=RecordState.REPORTED))
    seeded_session.flush()

    with pytest.raises(ImmutableRecordError):
        record_service.register_progress(seeded_session, today, [_log(material.id)], today)


def test_register_progress_updates_existing_study_log_for_same_material(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record_service.register_progress(seeded_session, today, [_log(material.id)], today)
    record = record_service.register_progress(
        seeded_session, today, [_log(material.id, minutes_spent=45, amount_completed=15)], today
    )

    assert len(record.study_logs) == 1
    assert record.study_logs[0].amount_completed == 15
    assert record.study_logs[0].minutes_spent == 45


def test_register_progress_reading_items_succeed_when_only_exam_is_reported(seeded_session):
    """資格勉強が確定済みでも、読書に入力があれば読書分のみ登録できる
    （カテゴリ単位のガード、仕様変更2026-09-05）。"""
    reading_goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, reading_goal)
    today = dt.date(2026, 3, 10)
    seeded_session.add(DailyRecord(record_date=today, exam_record_state=RecordState.REPORTED))
    seeded_session.flush()

    record = record_service.register_progress(
        seeded_session, today, [], today, [_reading_log(book.id)]
    )

    assert record.reading_record_state == RecordState.PROGRESS_ONLY
    assert record.exam_record_state == RecordState.REPORTED


def test_register_progress_rejects_unknown_material(seeded_session):
    today = dt.date(2026, 3, 10)

    with pytest.raises(NotFoundError):
        record_service.register_progress(seeded_session, today, [_log(9999)], today)


def test_finalize_record_rejects_unknown_goal_in_diary_entry(seeded_session):
    today = dt.date(2026, 3, 10)

    with pytest.raises(NotFoundError):
        record_service.finalize_record(seeded_session, today, [], [_diary(9999)], today)


def test_finalize_record_duplicate_goal_in_diary_entries_last_one_wins(seeded_session):
    """同一goal_idの日記エントリが複数渡された場合、後勝ちで1件に更新される。"""
    goal = _make_goal(seeded_session)
    today = dt.date(2026, 3, 10)

    record = record_service.finalize_record(
        seeded_session,
        today,
        [],
        [_diary(goal.id, "1件目", "学び1"), _diary(goal.id, "2件目", "学び2")],
        today,
    )

    entries = record_service.get_diary_entries(seeded_session, record)
    assert len(entries) == 1
    assert entries[0].diary_body == "2件目"


def test_register_progress_time_not_entered_is_excluded_from_speed_by_design(seeded_session):
    """時間未入力（minutes_spent=None）でも登録自体は成立する（実効速度算出からの除外はspeed_service側の責務）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service.register_progress(
        seeded_session, today, [_log(material.id, minutes_spent=None)], today
    )
    assert record.study_logs[0].minutes_spent is None


def test_register_progress_cycle_number_override_is_respected(seeded_session):
    """周回番号の既定値は算出値だが、利用者が明示指定した値で上書きできる（Phase4完了条件）。

    total_amount=10・planned_cycles=2の教材で1周目(10)を完了させると、既定値としての
    現在周回は2に進む。この状態で2件目のstudy_logにcycle_number=1を明示指定すると、
    既定値(2)ではなく指定値(1)が保存されることを検証する。
    """
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, total_amount=10.0, planned_cycles=2)
    today = dt.date(2026, 3, 10)

    record_service.register_progress(
        seeded_session, today, [_log(material.id, amount_completed=10, cycle_number=None)], today
    )
    assert cycle_service.get_material_progress(seeded_session, material).current_cycle == 2

    tomorrow = today + dt.timedelta(days=1)
    record = record_service.register_progress(
        seeded_session,
        tomorrow,
        [_log(material.id, amount_completed=2, cycle_number=1)],
        tomorrow,
    )

    assert record.study_logs[0].cycle_number == 1


def test_subjective_quality_rejects_non_integer_value(seeded_session):
    """1〜5の整数以外（例: 3.5）は範囲外と同様に拒否される（ロジック・プロンプト編14.1）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(
        seeded_session, goal, quality_metric_type=QualityMetricType.SUBJECTIVE
    )
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service.register_progress(
            seeded_session, today, [_log(material.id, quality_value=3.5)], today
        )


# --- finalize_record ---


def test_finalize_record_marks_reported_and_sets_diary(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service.finalize_record(
        seeded_session,
        today,
        [_log(material.id)],
        [_diary(goal.id, "今日はよく頑張った", "過去問を解いた")],
        today,
    )

    assert record.exam_record_state == RecordState.REPORTED
    assert record.exam_reported_at is not None
    entries = record_service.get_diary_entries(seeded_session, record)
    assert len(entries) == 1
    assert entries[0].goal_id == goal.id
    assert entries[0].diary_body == "今日はよく頑張った"
    assert entries[0].diary_learned == "過去問を解いた"


def test_finalize_record_allows_yesterday(seeded_session):
    """『前日』の判定はtoday引数を基準とし、境界値『当日または前日』を満たすこと（仕様書7.2）。"""
    today = dt.date(2026, 3, 10)
    yesterday = today - dt.timedelta(days=1)

    record = record_service.finalize_record(seeded_session, yesterday, [], [], today)
    assert record.exam_record_state == RecordState.REPORTED


def test_finalize_record_rejects_two_days_ago(seeded_session):
    today = dt.date(2026, 3, 10)
    two_days_ago = today - dt.timedelta(days=2)

    with pytest.raises(BackdateLimitExceededError):
        record_service.finalize_record(seeded_session, two_days_ago, [], [], today)


def test_finalize_record_rejects_future_date(seeded_session):
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service.finalize_record(seeded_session, today + dt.timedelta(days=1), [], [], today)


def test_finalize_record_rejects_already_reported(seeded_session):
    today = dt.date(2026, 3, 10)
    seeded_session.add(DailyRecord(record_date=today, exam_record_state=RecordState.REPORTED))
    seeded_session.flush()

    with pytest.raises(ImmutableRecordError):
        record_service.finalize_record(seeded_session, today, [], [], today)


def test_finalize_record_promotes_progress_only_record(seeded_session):
    """進捗のみ登録済→報告済への昇格（仕様書7.2の状態遷移）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record_service.register_progress(seeded_session, today, [_log(material.id)], today)
    record = record_service.finalize_record(seeded_session, today, [], [], today)

    assert record.exam_record_state == RecordState.REPORTED
    assert len(record.study_logs) == 1  # 進捗のみ登録時点のstudy_logが保持される


# --- 読書記録（reading_log。実装フェーズ分割計画書Phase15） ---


def _make_reading_goal(session):
    goal = Goal(
        category=GoalCategory.READING,
        name="読書目標",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_book(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        title="書籍A",
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 12, 31),
    )
    defaults.update(overrides)
    book = Book(**defaults)
    session.add(book)
    session.flush()
    return book


def _reading_log(book_id, **overrides):
    defaults = dict(
        book_id=book_id, recall_body="今日読んだ内容の想起", pages_read=10, current_page=10
    )
    defaults.update(overrides)
    return ReadingLogItem(**defaults)


def test_register_progress_creates_reading_log(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service.register_progress(
        seeded_session, today, [], today, [_reading_log(book.id)]
    )

    assert len(record.reading_logs) == 1
    assert record.reading_logs[0].recall_body == "今日読んだ内容の想起"


def test_register_progress_rejects_when_both_lists_empty(seeded_session):
    """study_logs・reading_logsの両方が空の登録は拒否する（無意味な登録のため）。"""
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service.register_progress(seeded_session, today, [], today, [])


def test_register_progress_accepts_reading_only_without_study_logs(seeded_session):
    """資格試験のstudy_logsが空でも、読書のreading_logsのみで登録できる
    （両カテゴリの目標が同時進行しうるため、study_logsを必須にできない）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service.register_progress(
        seeded_session, today, [], today, [_reading_log(book.id)]
    )

    assert record.reading_record_state == RecordState.PROGRESS_ONLY
    assert record.exam_record_state is None


def test_register_progress_rejects_unknown_book(seeded_session):
    today = dt.date(2026, 3, 10)

    with pytest.raises(NotFoundError):
        record_service.register_progress(seeded_session, today, [], today, [_reading_log(9999)])


def test_register_progress_updates_existing_reading_log_for_same_book(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record_service.register_progress(seeded_session, today, [], today, [_reading_log(book.id)])
    record = record_service.register_progress(
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

    record = record_service.finalize_reading_record(
        seeded_session, today, [_reading_log(book.id)], today
    )

    assert record.reading_record_state == RecordState.REPORTED
    assert record.exam_record_state is None
    assert len(record.reading_logs) == 1


def test_finalize_record_and_finalize_reading_record_are_independent(seeded_session):
    """資格勉強（EXAM）の確定と読書の確定は互いに影響しない
    （仕様変更2026-09-05のコア要件: 一方を確定しても他方は引き続き入力・確定できる）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record_service.finalize_record(
        seeded_session, today, [], [_diary(goal.id, "今日の行動所感", "学んだこと")], today
    )
    record = record_service.finalize_reading_record(
        seeded_session, today, [_reading_log(book.id)], today
    )

    assert record.exam_record_state == RecordState.REPORTED
    assert record.reading_record_state == RecordState.REPORTED
    entries = record_service.get_diary_entries(seeded_session, record)
    assert entries[0].diary_body == "今日の行動所感"


def test_finalize_reading_record_allows_reading_log_without_diary(seeded_session):
    """想起のみの入力でも確定できる（要件定義書R-65「数値実績の入力を必須としない」）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service.finalize_reading_record(
        seeded_session, today, [_reading_log(book.id)], today
    )

    assert record.reading_record_state == RecordState.REPORTED
    assert len(record.reading_logs) == 1


def test_finalize_reading_record_rejects_already_reported(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)
    record_service.finalize_reading_record(seeded_session, today, [_reading_log(book.id)], today)

    with pytest.raises(ImmutableRecordError):
        record_service.finalize_reading_record(
            seeded_session, today, [_reading_log(book.id)], today
        )


def test_finalize_reading_record_does_not_block_exam_finalize(seeded_session):
    """読書を確定した後でも、資格勉強は引き続き確定できる（仕様変更2026-09-05）。"""
    exam_goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, exam_goal)
    reading_goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, reading_goal)
    today = dt.date(2026, 3, 10)

    record_service.finalize_reading_record(seeded_session, today, [_reading_log(book.id)], today)
    record = record_service.finalize_record(seeded_session, today, [_log(material.id)], [], today)

    assert record.reading_record_state == RecordState.REPORTED
    assert record.exam_record_state == RecordState.REPORTED


# --- 業務記録（work_logs、実装フェーズ分割計画書Phase21） ---


def _make_work_goal(session, status=GoalStatus.ACTIVE, name="仕事目標A"):
    goal = Goal(
        category=GoalCategory.WORK,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=status,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_work_assignment(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        expected_content="想定業務内容",
        start_date=dt.date(2026, 1, 1),
    )
    defaults.update(overrides)
    work_assignment = WorkAssignment(**defaults)
    session.add(work_assignment)
    session.flush()
    return work_assignment


def _work_log(work_assignment_id, **overrides):
    defaults = dict(work_assignment_id=work_assignment_id, body="今日の業務内容")
    defaults.update(overrides)
    return WorkLogItem(**defaults)


def test_register_progress_creates_work_log(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service.register_progress(
        seeded_session, today, [], today, work_items=[_work_log(work_assignment.id)]
    )

    assert len(record.work_logs) == 1
    assert record.work_logs[0].body == "今日の業務内容"


def test_register_progress_rejects_when_all_lists_empty(seeded_session):
    """study_logs・reading_logs・work_logsすべてが空の登録は拒否する（無意味な登録のため）。"""
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service.register_progress(seeded_session, today, [], today)


def test_register_progress_accepts_work_only_without_study_logs(seeded_session):
    """資格試験のstudy_logsが空でも、仕事のwork_logsのみで登録できる
    （複数カテゴリの目標が同時進行しうるため、study_logsを必須にできない）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service.register_progress(
        seeded_session, today, [], today, work_items=[_work_log(work_assignment.id)]
    )

    assert record.work_record_state == RecordState.PROGRESS_ONLY
    assert record.exam_record_state is None


def test_register_progress_rejects_unknown_work_assignment(seeded_session):
    today = dt.date(2026, 3, 10)

    with pytest.raises(NotFoundError):
        record_service.register_progress(
            seeded_session, today, [], today, work_items=[_work_log(9999)]
        )


def test_register_progress_updates_existing_work_log_for_same_assignment(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record_service.register_progress(
        seeded_session, today, [], today, work_items=[_work_log(work_assignment.id)]
    )
    record = record_service.register_progress(
        seeded_session,
        today,
        [],
        today,
        work_items=[_work_log(work_assignment.id, body="上書き後の業務内容")],
    )

    assert len(record.work_logs) == 1
    assert record.work_logs[0].body == "上書き後の業務内容"


def test_finalize_work_record_persists_work_log(seeded_session):
    """仕事の確定は/finalize（EXAM）とは独立した専用関数（仕様変更2026-09-05）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service.finalize_work_record(
        seeded_session, today, [_work_log(work_assignment.id)], today
    )

    assert record.work_record_state == RecordState.REPORTED
    assert record.exam_record_state is None
    assert len(record.work_logs) == 1


def test_finalize_work_record_allows_work_log_without_study_or_diary(seeded_session):
    """業務記録のみの入力でも確定できる（要件定義書R-75「数値実績の入力を必須としない」）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service.finalize_work_record(
        seeded_session, today, [_work_log(work_assignment.id)], today
    )

    assert record.work_record_state == RecordState.REPORTED
    assert len(record.work_logs) == 1


def test_finalize_work_record_rejects_already_reported(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    today = dt.date(2026, 3, 10)
    record_service.finalize_work_record(
        seeded_session, today, [_work_log(work_assignment.id)], today
    )

    with pytest.raises(ImmutableRecordError):
        record_service.finalize_work_record(
            seeded_session, today, [_work_log(work_assignment.id)], today
        )


def test_finalize_work_record_does_not_affect_exam_or_reading_state(seeded_session):
    """仕事を確定しても資格勉強・読書は未着手のまま引き続き入力・確定できる
    （仕様変更2026-09-05のコア要件）。"""
    exam_goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, exam_goal)
    reading_goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, reading_goal)
    work_goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, work_goal)
    today = dt.date(2026, 3, 10)

    record_service.finalize_work_record(
        seeded_session, today, [_work_log(work_assignment.id)], today
    )

    assert record_service.get_daily_record(seeded_session, today).exam_record_state is None
    assert record_service.get_daily_record(seeded_session, today).reading_record_state is None

    record_service.register_progress(seeded_session, today, [_log(material.id)], today)
    record = record_service.finalize_reading_record(
        seeded_session, today, [_reading_log(book.id)], today
    )

    assert record.exam_record_state == RecordState.PROGRESS_ONLY
    assert record.reading_record_state == RecordState.REPORTED
    assert record.work_record_state == RecordState.REPORTED


# --- 品質指標の正規化（ロジック・プロンプト編14.1） ---


def test_subjective_quality_is_normalized(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(
        seeded_session, goal, quality_metric_type=QualityMetricType.SUBJECTIVE
    )
    today = dt.date(2026, 3, 10)

    record = record_service.register_progress(
        seeded_session, today, [_log(material.id, quality_value=3)], today
    )
    assert record.study_logs[0].quality_value == 60.0


def test_subjective_quality_rejects_out_of_range(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(
        seeded_session, goal, quality_metric_type=QualityMetricType.SUBJECTIVE
    )
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service.register_progress(
            seeded_session, today, [_log(material.id, quality_value=6)], today
        )


def test_objective_quality_passes_through(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, quality_metric_type=QualityMetricType.OBJECTIVE)
    today = dt.date(2026, 3, 10)

    record = record_service.register_progress(
        seeded_session, today, [_log(material.id, quality_value=72.5)], today
    )
    assert record.study_logs[0].quality_value == 72.5


def test_objective_quality_rejects_out_of_range(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, quality_metric_type=QualityMetricType.OBJECTIVE)
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service.register_progress(
            seeded_session, today, [_log(material.id, quality_value=150)], today
        )


def test_quality_rejects_value_when_metric_type_is_none(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, quality_metric_type=QualityMetricType.NONE)
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service.register_progress(
            seeded_session, today, [_log(material.id, quality_value=50)], today
        )


# --- コメント ---


def test_add_comment_requires_existing_record(seeded_session):
    today = dt.date(2026, 3, 10)
    with pytest.raises(NotFoundError):
        record_service.add_comment(seeded_session, today, "コメント")


def test_add_update_delete_comment(seeded_session):
    today = dt.date(2026, 3, 10)
    seeded_session.add(DailyRecord(record_date=today, exam_record_state=RecordState.REPORTED))
    seeded_session.flush()

    comment = record_service.add_comment(seeded_session, today, "初回コメント")
    assert comment.body == "初回コメント"

    record_service.update_comment(seeded_session, comment, "修正後コメント")
    assert comment.body == "修正後コメント"

    record_service.delete_comment(seeded_session, comment)
    assert seeded_session.get(RecordComment, comment.id) is None


def test_get_comment_missing_raises_not_found(seeded_session):
    with pytest.raises(NotFoundError):
        record_service.get_comment(seeded_session, 9999)


# --- 日次ノルマ（GET /records/{date}/quota） ---


def test_compute_daily_quota_includes_active_goal_materials_before_due_date(seeded_session):
    goal = _make_goal(seeded_session, status=GoalStatus.ACTIVE)
    material = _make_material(
        seeded_session,
        goal,
        due_date=dt.date(2026, 3, 31),
        total_amount=100.0,
        planned_cycles=1,
        unit_label="問",
        quality_metric_type=QualityMetricType.SUBJECTIVE,
    )
    target_date = dt.date(2026, 3, 10)  # 火曜（平日=PLAN既定）

    items = record_service.compute_daily_quota(seeded_session, target_date)

    assert len(items) == 1
    assert items[0].material_id == material.id
    assert items[0].daily_quota > 0
    # 実績入力欄（SC-06/SC-07）の単位表示・品質指標の入力形式切替に必要な値（仕様書6.5）。
    assert items[0].unit_label == "問"
    assert items[0].quality_metric_type == QualityMetricType.SUBJECTIVE
    # 複数目標が同時進行する場合の表示グルーピング（ダッシュボード/日次報告）に必要な値。
    assert items[0].goal_id == goal.id
    assert items[0].goal_name == goal.name


def test_compute_daily_quota_attributes_each_material_to_its_own_goal(seeded_session):
    """複数目標が同時進行する場合、教材ごとに正しい目標へ帰属すること（L-04関連）。"""
    goal_a = _make_goal(seeded_session, name="目標A")
    goal_b = _make_goal(seeded_session, name="目標B")
    material_a = _make_material(seeded_session, goal_a, due_date=dt.date(2026, 3, 31))
    material_b = _make_material(seeded_session, goal_b, due_date=dt.date(2026, 3, 31))
    target_date = dt.date(2026, 3, 10)

    items = record_service.compute_daily_quota(seeded_session, target_date)

    items_by_material = {item.material_id: item for item in items}
    assert items_by_material[material_a.id].goal_id == goal_a.id
    assert items_by_material[material_a.id].goal_name == "目標A"
    assert items_by_material[material_b.id].goal_id == goal_b.id
    assert items_by_material[material_b.id].goal_name == "目標B"


def test_compute_daily_quota_excludes_past_due_material(seeded_session):
    goal = _make_goal(seeded_session, status=GoalStatus.ACTIVE)
    _make_material(seeded_session, goal, due_date=dt.date(2026, 3, 1))

    items = record_service.compute_daily_quota(seeded_session, dt.date(2026, 3, 10))
    assert items == []


def test_compute_daily_quota_excludes_material_before_start_date(seeded_session):
    goal = _make_goal(seeded_session, status=GoalStatus.ACTIVE)
    _make_material(
        seeded_session,
        goal,
        start_date=dt.date(2026, 4, 1),
        due_date=dt.date(2026, 12, 31),
    )

    items = record_service.compute_daily_quota(seeded_session, dt.date(2026, 3, 10))
    assert items == []


def test_compute_daily_quota_excludes_inactive_goal(seeded_session):
    goal = _make_goal(seeded_session, status=GoalStatus.PAUSED)
    _make_material(seeded_session, goal, due_date=dt.date(2026, 12, 31))

    items = record_service.compute_daily_quota(seeded_session, dt.date(2026, 3, 10))
    assert items == []


def test_compute_daily_quota_excludes_inactive_material(seeded_session):
    goal = _make_goal(seeded_session, status=GoalStatus.ACTIVE)
    _make_material(seeded_session, goal, due_date=dt.date(2026, 12, 31), is_active=False)

    items = record_service.compute_daily_quota(seeded_session, dt.date(2026, 3, 10))
    assert items == []


# --- カレンダー（GET /calendar） ---


def test_get_calendar_days_combines_day_type_and_record_state(seeded_session):
    seeded_session.add(
        DailyRecord(record_date=dt.date(2026, 3, 10), exam_record_state=RecordState.REPORTED)
    )
    seeded_session.flush()

    days = record_service.get_calendar_days(
        seeded_session, dt.date(2026, 3, 9), dt.date(2026, 3, 10)
    )

    assert len(days) == 2
    reported_day = next(d for d in days if d.target_date == dt.date(2026, 3, 10))
    assert reported_day.record_state == RecordState.REPORTED
    unreported_day = next(d for d in days if d.target_date == dt.date(2026, 3, 9))
    assert unreported_day.record_state is None


def test_get_calendar_days_reports_partial_category_as_progress_only(seeded_session):
    """資格勉強のみ確定・読書は未確定の日は、カレンダー上は「進捗のみ登録済」として
    表示される（触れたカテゴリのうち1つでも未確定なら集約はPROGRESS_ONLY、仕様変更
    2026-09-05のaggregate_record_stateルール）。"""
    seeded_session.add(
        DailyRecord(
            record_date=dt.date(2026, 3, 10),
            exam_record_state=RecordState.REPORTED,
            reading_record_state=RecordState.PROGRESS_ONLY,
        )
    )
    seeded_session.flush()

    days = record_service.get_calendar_days(
        seeded_session, dt.date(2026, 3, 10), dt.date(2026, 3, 10)
    )

    assert days[0].record_state == RecordState.PROGRESS_ONLY


def test_get_calendar_days_returns_empty_when_range_inverted(seeded_session):
    """境界値: 期間が逆転している場合に例外が発生しないこと（Phase2完了条件の踏襲）。"""
    days = record_service.get_calendar_days(
        seeded_session, dt.date(2026, 3, 10), dt.date(2026, 3, 1)
    )
    assert days == []


# --- aggregate_record_state（カテゴリ横断の単一状態算出、仕様変更2026-09-05） ---


def test_aggregate_record_state_none_when_no_category_touched():
    assert record_service.aggregate_record_state(None, None, None) is None


def test_aggregate_record_state_reported_when_only_touched_category_is_reported():
    """触れていないカテゴリ（None）は判定から除外され、確定のブロッカーにならない。"""
    assert (
        record_service.aggregate_record_state(RecordState.REPORTED, None, None)
        == RecordState.REPORTED
    )


def test_aggregate_record_state_reported_when_all_touched_categories_reported():
    assert (
        record_service.aggregate_record_state(
            RecordState.REPORTED, RecordState.REPORTED, RecordState.REPORTED
        )
        == RecordState.REPORTED
    )


def test_aggregate_record_state_progress_only_when_any_touched_category_is_progress_only():
    assert (
        record_service.aggregate_record_state(RecordState.REPORTED, RecordState.PROGRESS_ONLY, None)
        == RecordState.PROGRESS_ONLY
    )


def test_aggregate_record_state_progress_only_when_single_category_in_progress():
    assert (
        record_service.aggregate_record_state(None, None, RecordState.PROGRESS_ONLY)
        == RecordState.PROGRESS_ONLY
    )
