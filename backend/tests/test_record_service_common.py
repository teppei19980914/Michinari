"""record_service_common のテスト（設計書データ構造編5.4・6.2、仕様書6.4〜6.7・7.2・14章、
実装フェーズ分割計画書Phase4・S02）。register_progressのディスパッチャとしての検証
（カテゴリを問わない共通の入力検証、カテゴリ横断の相互独立性）・コメント・カレンダー・
aggregate_record_stateを対象とする。カテゴリ固有の実績登録・確定のテストは
test_record_service_exam.py・test_record_service_reading.py・test_record_service_work.py
を参照（実装フェーズ分割計画書S02、test_record_service.pyからの分割）。
"""

import datetime as dt

import pytest

from app.constants.enums import GoalCategory, GoalStatus, QualityMetricType, RecordState
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, RecordComment
from app.models.work import WorkAssignment
from app.services import (
    record_service_common,
    record_service_exam,
    record_service_reading,
    record_service_work,
)
from app.services.exceptions import ImmutableRecordError, NotFoundError, ValidationError
from app.services.record_service_exam import StudyLogItem
from app.services.record_service_work import WorkLogItem
from tests import reading_helpers
from tests.diary_helpers import diary_item as _diary
from tests.diary_helpers import make_exam_goal as _make_goal


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


def _make_reading_goal(session):
    return reading_helpers.make_reading_goal(session, name="読書目標")


def _make_book(session, goal, **overrides):
    return reading_helpers.make_book(session, goal.id, **overrides)


def _reading_log(book_id, **overrides):
    return reading_helpers.reading_log_item(book_id, **overrides)


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


# --- register_progress（カテゴリを問わない共通の入力検証） ---


def test_register_progress_rejects_future_date(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service_common.register_progress(
            seeded_session, today + dt.timedelta(days=1), [_log(material.id)], today
        )


def test_register_progress_allows_far_past_date(seeded_session):
    """進捗のみ登録は『当日または前日以前』であり、任意の過去日を許容する（仕様書7.2）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
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
        record_service_common.register_progress(seeded_session, today, [_log(material.id)], today)


def test_register_progress_rejects_when_both_lists_empty(seeded_session):
    """study_logs・reading_logsの両方が空の登録は拒否する（無意味な登録のため）。"""
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service_common.register_progress(seeded_session, today, [], today, [])


def test_register_progress_rejects_when_all_lists_empty(seeded_session):
    """study_logs・reading_logs・work_logsすべてが空の登録は拒否する（無意味な登録のため）。"""
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service_common.register_progress(seeded_session, today, [], today)


# --- register_progress（カテゴリ横断の相互独立性、仕様変更2026-09-05） ---


def test_register_progress_reading_items_succeed_when_only_exam_is_reported(seeded_session):
    """資格勉強が確定済みでも、読書に入力があれば読書分のみ登録できる
    （カテゴリ単位のガード、仕様変更2026-09-05）。"""
    reading_goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, reading_goal)
    today = dt.date(2026, 3, 10)
    seeded_session.add(DailyRecord(record_date=today, exam_record_state=RecordState.REPORTED))
    seeded_session.flush()

    record = record_service_common.register_progress(
        seeded_session, today, [], today, [_reading_log(book.id)]
    )

    assert record.reading_record_state == RecordState.PROGRESS_ONLY
    assert record.exam_record_state == RecordState.REPORTED


def test_finalize_record_and_finalize_reading_record_are_independent(seeded_session):
    """資格勉強（EXAM）の確定と読書の確定は互いに影響しない
    （仕様変更2026-09-05のコア要件: 一方を確定しても他方は引き続き入力・確定できる）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record_service_exam.finalize_record(
        seeded_session, today, [], [_diary(goal.id, "今日の行動所感", "学んだこと")], today
    )
    record = record_service_reading.finalize_reading_record(
        seeded_session, today, [_reading_log(book.id)], today
    )

    assert record.exam_record_state == RecordState.REPORTED
    assert record.reading_record_state == RecordState.REPORTED
    entries = record_service_exam.get_diary_entries(seeded_session, record)
    assert entries[0].diary_body == "今日の行動所感"


def test_finalize_reading_record_does_not_block_exam_finalize(seeded_session):
    """読書を確定した後でも、資格勉強は引き続き確定できる（仕様変更2026-09-05）。"""
    exam_goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, exam_goal)
    reading_goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, reading_goal)
    today = dt.date(2026, 3, 10)

    record_service_reading.finalize_reading_record(
        seeded_session, today, [_reading_log(book.id)], today
    )
    record = record_service_exam.finalize_record(
        seeded_session, today, [_log(material.id)], [], today
    )

    assert record.reading_record_state == RecordState.REPORTED
    assert record.exam_record_state == RecordState.REPORTED


def test_register_progress_records_all_categories_in_one_request(seeded_session):
    """資格試験・読書・仕事を3つまとめて1リクエストで登録できる。

    進捗のみ登録画面（SC-07）は確定（finalize）と違いカテゴリ別の操作を持たず、
    登録1回で着手中の全カテゴリ分をまとめて送る（仕様書6.6、1.1（改21））。
    カテゴリ単体の登録は個別に検証しているが、同時に送った場合は未検証だった。
    """
    exam_goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, exam_goal)
    reading_goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, reading_goal)
    work_goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, work_goal)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
        seeded_session,
        today,
        [_log(material.id)],
        today,
        [_reading_log(book.id)],
        [_work_log(work_assignment.id)],
    )

    assert len(record.study_logs) == 1
    assert len(record.reading_logs) == 1
    assert len(record.work_logs) == 1
    assert record.exam_record_state == RecordState.PROGRESS_ONLY
    assert record.reading_record_state == RecordState.PROGRESS_ONLY
    assert record.work_record_state == RecordState.PROGRESS_ONLY


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

    record_service_work.finalize_work_record(
        seeded_session, today, [_work_log(work_assignment.id)], today
    )

    assert record_service_common.get_daily_record(seeded_session, today).exam_record_state is None
    assert (
        record_service_common.get_daily_record(seeded_session, today).reading_record_state is None
    )

    record_service_common.register_progress(seeded_session, today, [_log(material.id)], today)
    record = record_service_reading.finalize_reading_record(
        seeded_session, today, [_reading_log(book.id)], today
    )

    assert record.exam_record_state == RecordState.PROGRESS_ONLY
    assert record.reading_record_state == RecordState.REPORTED
    assert record.work_record_state == RecordState.REPORTED


# --- コメント ---


def test_add_comment_requires_existing_record(seeded_session):
    _make_goal(seeded_session, status=GoalStatus.ACTIVE)
    today = dt.date(2026, 3, 10)
    with pytest.raises(NotFoundError):
        record_service_common.add_comment(seeded_session, today, "コメント")


def test_add_update_delete_comment(seeded_session):
    _make_goal(seeded_session, status=GoalStatus.ACTIVE)
    today = dt.date(2026, 3, 10)
    seeded_session.add(DailyRecord(record_date=today, exam_record_state=RecordState.REPORTED))
    seeded_session.flush()

    comment = record_service_common.add_comment(seeded_session, today, "初回コメント")
    assert comment.body == "初回コメント"

    record_service_common.update_comment(seeded_session, comment, "修正後コメント")
    assert comment.body == "修正後コメント"

    record_service_common.delete_comment(seeded_session, comment)
    assert seeded_session.get(RecordComment, comment.id) is None


def test_get_comment_missing_raises_not_found(seeded_session):
    with pytest.raises(NotFoundError):
        record_service_common.get_comment(seeded_session, 9999)


# --- カレンダー（GET /calendar） ---


def test_get_calendar_days_combines_day_type_and_record_state(seeded_session):
    seeded_session.add(
        DailyRecord(record_date=dt.date(2026, 3, 10), exam_record_state=RecordState.REPORTED)
    )
    seeded_session.flush()

    days = record_service_common.get_calendar_days(
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

    days = record_service_common.get_calendar_days(
        seeded_session, dt.date(2026, 3, 10), dt.date(2026, 3, 10)
    )

    assert days[0].record_state == RecordState.PROGRESS_ONLY


def test_get_calendar_days_returns_empty_when_range_inverted(seeded_session):
    """境界値: 期間が逆転している場合に例外が発生しないこと（Phase2完了条件の踏襲）。"""
    days = record_service_common.get_calendar_days(
        seeded_session, dt.date(2026, 3, 10), dt.date(2026, 3, 1)
    )
    assert days == []


# --- aggregate_record_state（カテゴリ横断の単一状態算出、仕様変更2026-09-05） ---


def test_aggregate_record_state_none_when_no_category_touched():
    assert record_service_common.aggregate_record_state(None, None, None) is None


def test_aggregate_record_state_reported_when_only_touched_category_is_reported():
    """触れていないカテゴリ（None）は判定から除外され、確定のブロッカーにならない。"""
    assert (
        record_service_common.aggregate_record_state(RecordState.REPORTED, None, None)
        == RecordState.REPORTED
    )


def test_aggregate_record_state_reported_when_all_touched_categories_reported():
    assert (
        record_service_common.aggregate_record_state(
            RecordState.REPORTED, RecordState.REPORTED, RecordState.REPORTED
        )
        == RecordState.REPORTED
    )


def test_aggregate_record_state_progress_only_when_any_touched_category_is_progress_only():
    assert (
        record_service_common.aggregate_record_state(
            RecordState.REPORTED, RecordState.PROGRESS_ONLY, None
        )
        == RecordState.PROGRESS_ONLY
    )


def test_aggregate_record_state_progress_only_when_single_category_in_progress():
    assert (
        record_service_common.aggregate_record_state(None, None, RecordState.PROGRESS_ONLY)
        == RecordState.PROGRESS_ONLY
    )


class TestResolveRecordState:
    """カレンダー・ダッシュボード・本日取得・記録リマインドが共有する集約（Phase37）。

    4箇所へ写されていた展開を1つにまとめたもの。カテゴリが増えたときに直す箇所を
    1つにするのが狙いであるため、3カテゴリすべてを見ていることを確かめる。
    """

    def test_returns_none_for_a_day_without_a_record(self):
        assert record_service_common.resolve_record_state(None) is None

    def test_returns_none_when_no_category_was_touched(self, db_session):
        record = record_service_common.ensure_daily_record(db_session, dt.date(2026, 9, 13))

        assert record_service_common.resolve_record_state(record) is None

    @pytest.mark.parametrize(
        "column",
        ["exam_record_state", "reading_record_state", "work_record_state"],
        ids=["exam", "reading", "work"],
    )
    def test_reports_progress_for_any_single_category(self, db_session, column: str):
        record = record_service_common.ensure_daily_record(db_session, dt.date(2026, 9, 13))
        setattr(record, column, RecordState.PROGRESS_ONLY)

        assert record_service_common.resolve_record_state(record) == RecordState.PROGRESS_ONLY

    def test_reports_reported_only_when_every_touched_category_is_reported(self, db_session):
        record = record_service_common.ensure_daily_record(db_session, dt.date(2026, 9, 13))
        record.exam_record_state = RecordState.REPORTED
        record.reading_record_state = RecordState.REPORTED

        assert record_service_common.resolve_record_state(record) == RecordState.REPORTED

    def test_reports_progress_when_one_touched_category_is_unfinished(self, db_session):
        record = record_service_common.ensure_daily_record(db_session, dt.date(2026, 9, 13))
        record.exam_record_state = RecordState.REPORTED
        record.work_record_state = RecordState.PROGRESS_ONLY

        assert record_service_common.resolve_record_state(record) == RecordState.PROGRESS_ONLY


class TestCountReportedRecordsBefore:
    """観点提案プロンプトの閾値判定（S-4 4-3）。指定日より前の確定済み記録数を数える。"""

    def test_returns_zero_when_there_are_no_records(self, db_session):
        assert (
            record_service_common.count_reported_records_before(
                db_session, GoalCategory.EXAM, dt.date(2026, 9, 13)
            )
            == 0
        )

    def test_counts_only_the_given_category(self, db_session):
        record = record_service_common.ensure_daily_record(db_session, dt.date(2026, 9, 10))
        record.exam_record_state = RecordState.REPORTED
        record.reading_record_state = RecordState.REPORTED
        db_session.flush()

        assert (
            record_service_common.count_reported_records_before(
                db_session, GoalCategory.WORK, dt.date(2026, 9, 13)
            )
            == 0
        )
        assert (
            record_service_common.count_reported_records_before(
                db_session, GoalCategory.EXAM, dt.date(2026, 9, 13)
            )
            == 1
        )

    def test_excludes_records_on_or_after_the_given_date(self, db_session):
        earlier = record_service_common.ensure_daily_record(db_session, dt.date(2026, 9, 10))
        earlier.exam_record_state = RecordState.REPORTED
        same_day = record_service_common.ensure_daily_record(db_session, dt.date(2026, 9, 13))
        same_day.exam_record_state = RecordState.REPORTED
        db_session.flush()

        assert (
            record_service_common.count_reported_records_before(
                db_session, GoalCategory.EXAM, dt.date(2026, 9, 13)
            )
            == 1
        )

    def test_excludes_progress_only_records(self, db_session):
        record = record_service_common.ensure_daily_record(db_session, dt.date(2026, 9, 10))
        record.exam_record_state = RecordState.PROGRESS_ONLY
        db_session.flush()

        assert (
            record_service_common.count_reported_records_before(
                db_session, GoalCategory.EXAM, dt.date(2026, 9, 13)
            )
            == 0
        )


class TestHasAnyReportedRecord:
    """初回記録バナー（S-4 4-2）の非表示条件。カテゴリを問わず1件でもREPORTEDがあればTrue。"""

    def test_returns_false_when_there_are_no_records_at_all(self, db_session):
        assert record_service_common.has_any_reported_record(db_session) is False

    def test_returns_false_when_records_exist_but_none_are_reported(self, db_session):
        record = record_service_common.ensure_daily_record(db_session, dt.date(2026, 9, 13))
        record.exam_record_state = RecordState.PROGRESS_ONLY
        db_session.flush()

        assert record_service_common.has_any_reported_record(db_session) is False

    @pytest.mark.parametrize(
        "column",
        ["exam_record_state", "reading_record_state", "work_record_state"],
        ids=["exam", "reading", "work"],
    )
    def test_returns_true_when_any_single_category_is_reported(self, db_session, column: str):
        record = record_service_common.ensure_daily_record(db_session, dt.date(2026, 9, 13))
        setattr(record, column, RecordState.REPORTED)
        db_session.flush()

        assert record_service_common.has_any_reported_record(db_session) is True
