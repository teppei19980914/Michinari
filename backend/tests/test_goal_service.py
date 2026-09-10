"""goal_service の計画基準値の再設定ロジックのテスト（ロジック・プロンプト編7.1・12章）。"""

import datetime as dt

import pytest

from app.constants.enums import BaselineReason, DayType, GoalCategory, GoalStatus, RecordState
from app.models.book import Book
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import (
    ChatMessage,
    DailyGoalDiary,
    DailyRecord,
    ReadingLog,
    RecordComment,
    StudyLog,
    WorkLog,
)
from app.models.setting import CalendarDayOverride
from app.models.work import WorkAssignment
from app.services import goal_service
from app.services.exceptions import (
    BookHasReadingLogsError,
    InvalidStateTransitionError,
    MaterialHasStudyLogsError,
    WorkAssignmentHasWorkLogsError,
)


def _make_goal(db_session, status=GoalStatus.ACTIVE, name="目標A") -> Goal:
    goal = Goal(name=name, start_date=dt.date(2026, 1, 1), status=status)
    db_session.add(goal)
    db_session.flush()
    return goal


def _make_material(db_session, goal_id: int, **overrides) -> Material:
    defaults = dict(
        goal_id=goal_id,
        name="教材A",
        unit_label="ページ",
        total_amount=100.0,
        planned_cycles=1,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 1, 10),
        display_order=1,
    )
    defaults.update(overrides)
    material = Material(**defaults)
    db_session.add(material)
    db_session.flush()
    return material


def _override_all_plan(db_session, date_from: dt.date, date_to: dt.date) -> None:
    d = date_from
    while d <= date_to:
        db_session.add(CalendarDayOverride(target_date=d, day_type=DayType.PLAN))
        d += dt.timedelta(days=1)


def test_record_baseline_for_material_before_start_date_uses_start_date_quota(db_session):
    """開始日前に基準値を記録する場合、todayではなくstart_date時点のノルマを基準値とする。

    quota_service.compute_material_quotaは today < start_date のとき0を返す（7.1式の
    S(m)≤T条件）。基準値算出にそのまま today を渡すと baseline_daily_quota が0で固定され、
    開始日到来後にペースが乱れても check_warning の「baseline<=0なら判定しない」ガードで
    永久に警告が発火しなくなる（基準値の再設定契機はユーザー操作のみで、開始日到来による
    自動再設定は存在しないため）。max(today, start_date) を用いることでこれを防ぐ。
    """
    goal = _make_goal(db_session)
    material = _make_material(
        db_session, goal.id, start_date=dt.date(2026, 1, 5), due_date=dt.date(2026, 1, 10)
    )
    _override_all_plan(db_session, dt.date(2026, 1, 1), dt.date(2026, 1, 10))

    baseline = goal_service.record_baseline_for_material(
        db_session,
        material,
        BaselineReason.INITIAL,
        today=dt.date(2026, 1, 1),
        treat_holiday_as_buffer=True,
    )

    # start_date(1/5)〜due_date(1/10)の6日がすべてPLAN、remainingは100のまま
    assert baseline.baseline_daily_quota == 100 / 6
    assert baseline.baseline_daily_quota > 0
    # plan_days_at_baselineもquotaと同じ起点（start_date）で揃え、
    # baseline_daily_quota * plan_days_at_baseline = remaining_at_baseline の関係を保つ
    # （quotaだけ起点をずらしplan_daysをtodayのままにすると、この関係が崩れて
    # リプラン履歴表示・AI向け状況出力の数値が矛盾する）。
    assert baseline.plan_days_at_baseline == 6
    assert baseline.baseline_daily_quota * baseline.plan_days_at_baseline == pytest.approx(
        baseline.remaining_at_baseline
    )


def test_record_baseline_for_material_on_or_after_start_date_uses_today_quota(db_session):
    """開始日が到来済みの場合は従来どおりtoday時点のノルマを基準値とする（回帰確認）。"""
    goal = _make_goal(db_session)
    material = _make_material(
        db_session, goal.id, start_date=dt.date(2026, 1, 1), due_date=dt.date(2026, 1, 10)
    )
    _override_all_plan(db_session, dt.date(2026, 1, 1), dt.date(2026, 1, 10))

    baseline = goal_service.record_baseline_for_material(
        db_session,
        material,
        BaselineReason.INITIAL,
        today=dt.date(2026, 1, 1),
        treat_holiday_as_buffer=True,
    )

    assert baseline.baseline_daily_quota == 100 / 10


# --- アーカイブ・完全削除（要件定義書R-61〜R-63、仕様書7.1.1、データ構造編4.2） ---


def _make_daily_record(db_session, record_date: dt.date, **overrides) -> DailyRecord:
    defaults = dict(record_date=record_date, exam_record_state=RecordState.PROGRESS_ONLY)
    defaults.update(overrides)
    record = DailyRecord(**defaults)
    db_session.add(record)
    db_session.flush()
    return record


def _make_study_log(
    db_session, daily_record_id: int, material_id: int, cycle_number: int = 1
) -> StudyLog:
    log = StudyLog(
        daily_record_id=daily_record_id,
        material_id=material_id,
        amount_completed=1.0,
        cycle_number=cycle_number,
    )
    db_session.add(log)
    db_session.flush()
    return log


def _make_diary_entry(
    db_session, daily_record_id: int, goal_id: int, **overrides
) -> DailyGoalDiary:
    defaults = dict(daily_record_id=daily_record_id, goal_id=goal_id, diary_body="日記")
    defaults.update(overrides)
    entry = DailyGoalDiary(**defaults)
    db_session.add(entry)
    db_session.flush()
    return entry


def _make_reading_goal(db_session, status=GoalStatus.ACTIVE, name="読書目標A") -> Goal:
    goal = Goal(
        category=GoalCategory.READING,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=status,
    )
    db_session.add(goal)
    db_session.flush()
    return goal


def _make_book(db_session, goal_id: int, **overrides) -> Book:
    defaults = dict(
        goal_id=goal_id,
        title="書籍A",
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 12, 31),
    )
    defaults.update(overrides)
    book = Book(**defaults)
    db_session.add(book)
    db_session.flush()
    return book


def _make_reading_log(db_session, daily_record_id: int, book_id: int, **overrides) -> ReadingLog:
    defaults = dict(daily_record_id=daily_record_id, book_id=book_id, recall_body="想起")
    defaults.update(overrides)
    log = ReadingLog(**defaults)
    db_session.add(log)
    db_session.flush()
    return log


def _make_work_goal(db_session, status=GoalStatus.ACTIVE, name="仕事目標A") -> Goal:
    goal = Goal(
        category=GoalCategory.WORK,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=status,
    )
    db_session.add(goal)
    db_session.flush()
    return goal


def _make_work_assignment(db_session, goal_id: int, **overrides) -> WorkAssignment:
    defaults = dict(
        goal_id=goal_id,
        expected_content="想定業務内容",
        start_date=dt.date(2026, 1, 1),
    )
    defaults.update(overrides)
    work_assignment = WorkAssignment(**defaults)
    db_session.add(work_assignment)
    db_session.flush()
    return work_assignment


def _make_work_log(
    db_session, daily_record_id: int, work_assignment_id: int, **overrides
) -> WorkLog:
    defaults = dict(
        daily_record_id=daily_record_id, work_assignment_id=work_assignment_id, body="業務内容"
    )
    defaults.update(overrides)
    log = WorkLog(**defaults)
    db_session.add(log)
    db_session.flush()
    return log


def test_archive_goal_rejects_active_status(db_session):
    goal = _make_goal(db_session, status=GoalStatus.ACTIVE)
    with pytest.raises(InvalidStateTransitionError):
        goal_service.archive_goal(db_session, goal)


def test_archive_draft_goal_succeeds(db_session):
    """下書き（一時保存）中の目標もアーカイブできる（進行中でなければ対象、仕様書7.1.1）。"""
    goal = _make_goal(db_session, status=GoalStatus.DRAFT)
    goal_service.archive_goal(db_session, goal)
    assert goal.archived_at is not None
    assert goal.status == GoalStatus.DRAFT


def test_archive_paused_goal_succeeds(db_session):
    goal = _make_goal(db_session, status=GoalStatus.PAUSED)
    goal_service.archive_goal(db_session, goal)
    assert goal.archived_at is not None
    assert goal.status == GoalStatus.PAUSED


def test_activate_archived_draft_goal_is_rejected(db_session):
    """アーカイブ中は先に復元しないと開始できない（新規に発生する遷移の穴の防止）。"""
    goal = _make_goal(db_session, status=GoalStatus.DRAFT)
    goal_service.archive_goal(db_session, goal)
    with pytest.raises(InvalidStateTransitionError):
        goal_service.activate_goal(db_session, goal)


def test_resume_archived_paused_goal_is_rejected(db_session):
    """アーカイブ中は先に復元しないと再開できない（新規に発生する遷移の穴の防止）。"""
    goal = _make_goal(db_session, status=GoalStatus.PAUSED)
    goal_service.archive_goal(db_session, goal)
    with pytest.raises(InvalidStateTransitionError):
        goal_service.resume_goal(db_session, goal)


def test_delete_archived_draft_goal_is_rejected(db_session):
    """アーカイブ中の下書きは即時削除ではなく復元または完全削除の経路に統一する。"""
    goal = _make_goal(db_session, status=GoalStatus.DRAFT)
    goal_service.archive_goal(db_session, goal)
    with pytest.raises(InvalidStateTransitionError):
        goal_service.delete_goal(db_session, goal)


def test_delete_draft_goal_succeeds(db_session):
    goal = _make_goal(db_session, status=GoalStatus.DRAFT)
    goal_id = goal.id
    goal_service.delete_goal(db_session, goal)
    assert db_session.get(Goal, goal_id) is None


def test_archive_then_unarchive_goal_round_trip(db_session):
    goal = _make_goal(db_session, status=GoalStatus.CLOSED_WITHOUT_RESULT)

    goal_service.archive_goal(db_session, goal)
    assert goal.archived_at is not None
    assert goal.status == GoalStatus.CLOSED_WITHOUT_RESULT

    goal_service.unarchive_goal(db_session, goal)
    assert goal.archived_at is None
    # 復元してもstatusはクローズ済みのまま変わらない（仕様書7.1.1）。
    assert goal.status == GoalStatus.CLOSED_WITHOUT_RESULT


def test_archive_already_archived_goal_is_rejected(db_session):
    goal = _make_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    goal_service.archive_goal(db_session, goal)
    with pytest.raises(InvalidStateTransitionError):
        goal_service.archive_goal(db_session, goal)


def test_unarchive_non_archived_goal_is_rejected(db_session):
    goal = _make_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    with pytest.raises(InvalidStateTransitionError):
        goal_service.unarchive_goal(db_session, goal)


def test_delete_archived_goal_requires_archived_goal(db_session):
    goal = _make_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    with pytest.raises(InvalidStateTransitionError):
        goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=True)


def test_delete_archived_goal_without_cascade_rejects_when_study_logs_remain(db_session):
    goal = _make_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    material = _make_material(db_session, goal.id)
    record = _make_daily_record(db_session, dt.date(2026, 1, 5))
    _make_study_log(db_session, record.id, material.id)
    goal_service.archive_goal(db_session, goal)

    with pytest.raises(MaterialHasStudyLogsError):
        goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=False)


def test_delete_archived_goal_without_cascade_rejects_when_reading_logs_remain(db_session):
    """study_logのreading_log版（BookHasReadingLogsError、mainのアーカイブ機能との
    マージで追加した読書対応）。"""
    goal = _make_reading_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    book = _make_book(db_session, goal.id)
    record = _make_daily_record(db_session, dt.date(2026, 1, 5))
    _make_reading_log(db_session, record.id, book.id)
    goal_service.archive_goal(db_session, goal)

    with pytest.raises(BookHasReadingLogsError):
        goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=False)


def test_delete_archived_goal_without_cascade_succeeds_when_no_study_logs(db_session):
    goal = _make_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    _make_material(db_session, goal.id)
    goal_id = goal.id
    goal_service.archive_goal(db_session, goal)

    goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=False)

    assert db_session.get(Goal, goal_id) is None


def test_delete_archived_goal_with_cascade_removes_study_logs_and_deletes_empty_daily_record(
    db_session,
):
    """日記等が一切無いdaily_recordは、実績削除で空になった時点で物理削除する（データ構造編4.2）。"""
    goal = _make_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    material = _make_material(db_session, goal.id)
    record = _make_daily_record(db_session, dt.date(2026, 1, 5))
    _make_study_log(db_session, record.id, material.id)
    record_id = record.id
    goal_id = goal.id
    goal_service.archive_goal(db_session, goal)

    goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=True)

    assert db_session.get(Goal, goal_id) is None
    assert db_session.get(Material, material.id) is None
    assert db_session.get(DailyRecord, record_id) is None


def test_delete_archived_goal_with_cascade_removes_reading_logs_and_deletes_empty_daily_record(
    db_session,
):
    """study_logのreading_log版。_cascade_delete_activity_logsがbook経由のreading_logも
    削除し、空になったdaily_recordを物理削除すること（mainのアーカイブ機能とのマージで
    追加した読書対応）。"""
    goal = _make_reading_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    book = _make_book(db_session, goal.id)
    record = _make_daily_record(db_session, dt.date(2026, 1, 5))
    _make_reading_log(db_session, record.id, book.id)
    record_id = record.id
    goal_id = goal.id
    goal_service.archive_goal(db_session, goal)

    goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=True)

    assert db_session.get(Goal, goal_id) is None
    assert db_session.get(Book, book.id) is None
    assert db_session.get(DailyRecord, record_id) is None


def test_delete_archived_goal_without_cascade_rejects_when_work_logs_remain(db_session):
    """study_logのwork_log版（WorkAssignmentHasWorkLogsError、実装フェーズ分割計画書Phase21）。"""
    goal = _make_work_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    work_assignment = _make_work_assignment(db_session, goal.id)
    record = _make_daily_record(db_session, dt.date(2026, 1, 5))
    _make_work_log(db_session, record.id, work_assignment.id)
    goal_service.archive_goal(db_session, goal)

    with pytest.raises(WorkAssignmentHasWorkLogsError):
        goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=False)


def test_delete_archived_goal_with_cascade_removes_work_logs_and_deletes_empty_daily_record(
    db_session,
):
    """study_logのwork_log版。_cascade_delete_activity_logsがwork_assignment経由の
    work_logも削除し、空になったdaily_recordを物理削除すること（実装フェーズ分割計画書
    Phase21）。"""
    goal = _make_work_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    work_assignment = _make_work_assignment(db_session, goal.id)
    record = _make_daily_record(db_session, dt.date(2026, 1, 5))
    _make_work_log(db_session, record.id, work_assignment.id)
    record_id = record.id
    goal_id = goal.id
    goal_service.archive_goal(db_session, goal)

    goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=True)

    assert db_session.get(Goal, goal_id) is None
    assert db_session.get(WorkAssignment, work_assignment.id) is None
    assert db_session.get(DailyRecord, record_id) is None


def test_delete_archived_goal_without_cascade_succeeds_when_work_assignment_has_no_work_logs(
    db_session,
):
    """仕事目標の案件情報に業務記録が1件も無ければ、非cascadeでも削除を許可する
    （test_delete_archived_goal_without_cascade_succeeds_when_book_has_no_reading_logsの
    仕事版）。"""
    goal = _make_work_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    _make_work_assignment(db_session, goal.id)
    goal_id = goal.id
    goal_service.archive_goal(db_session, goal)

    goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=False)

    assert db_session.get(Goal, goal_id) is None


def test_delete_archived_goal_with_cascade_preserves_daily_record_shared_by_other_work_goal(
    db_session,
):
    """同じ日次報告に他の仕事目標のwork_logが残る場合、daily_record自体は保持する
    （test_delete_archived_goal_with_cascade_preserves_daily_record_shared_by_other_reading_goal
    の仕事版）。"""
    goal_a = _make_work_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT, name="削除対象")
    work_assignment_a = _make_work_assignment(db_session, goal_a.id)
    goal_b = _make_work_goal(db_session, name="他の仕事目標")
    work_assignment_b = _make_work_assignment(db_session, goal_b.id)

    record = _make_daily_record(db_session, dt.date(2026, 1, 5))
    _make_work_log(db_session, record.id, work_assignment_a.id)
    _make_work_log(db_session, record.id, work_assignment_b.id)
    record_id = record.id
    goal_a_id = goal_a.id
    goal_service.archive_goal(db_session, goal_a)

    goal_service.delete_archived_goal(db_session, goal_a, cascade_study_logs=True)

    assert db_session.get(Goal, goal_a_id) is None
    assert db_session.get(DailyRecord, record_id) is not None


def test_delete_archived_goal_without_cascade_succeeds_when_book_has_no_reading_logs(db_session):
    """読書目標の書籍に想起記録が1件も無ければ、非cascadeでも削除を許可する
    （test_delete_archived_goal_without_cascade_succeeds_when_no_study_logsの読書版）。"""
    goal = _make_reading_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    _make_book(db_session, goal.id)
    goal_id = goal.id
    goal_service.archive_goal(db_session, goal)

    goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=False)

    assert db_session.get(Goal, goal_id) is None


def test_delete_archived_goal_with_cascade_preserves_daily_record_shared_by_other_reading_goal(
    db_session,
):
    """同じ日次報告に他の読書目標のreading_logが残る場合、daily_record自体は保持する
    （test_delete_archived_goal_with_cascade_preserves_daily_record_shared_by_other_goalの
    読書版）。"""
    goal_a = _make_reading_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT, name="削除対象")
    book_a = _make_book(db_session, goal_a.id)
    goal_b = _make_reading_goal(db_session, name="他の読書目標")
    book_b = _make_book(db_session, goal_b.id)

    record = _make_daily_record(db_session, dt.date(2026, 1, 5))
    log_a = _make_reading_log(db_session, record.id, book_a.id)
    log_b = _make_reading_log(db_session, record.id, book_b.id)
    record_id = record.id
    goal_a_id = goal_a.id
    goal_service.archive_goal(db_session, goal_a)

    goal_service.delete_archived_goal(db_session, goal_a, cascade_study_logs=True)

    assert db_session.get(Goal, goal_a_id) is None
    assert db_session.get(ReadingLog, log_a.id) is None
    # goal_bの想起記録・daily_record自体は巻き添えにしない。
    assert db_session.get(DailyRecord, record_id) is not None
    assert db_session.get(ReadingLog, log_b.id) is not None


def test_delete_archived_goal_with_cascade_preserves_daily_record_shared_by_other_goal(
    db_session,
):
    """同じ日次報告に他goalの実績が残る場合、daily_record自体は保持する（データ構造編4.2）。"""
    goal_a = _make_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    material_a = _make_material(db_session, goal_a.id)
    goal_b = _make_goal(db_session, status=GoalStatus.ACTIVE)
    material_b = _make_material(db_session, goal_b.id)

    record = _make_daily_record(db_session, dt.date(2026, 1, 5))
    log_a = _make_study_log(db_session, record.id, material_a.id)
    log_b = _make_study_log(db_session, record.id, material_b.id)
    record_id = record.id
    log_b_id = log_b.id
    goal_a_id = goal_a.id
    goal_service.archive_goal(db_session, goal_a)

    goal_service.delete_archived_goal(db_session, goal_a, cascade_study_logs=True)

    assert db_session.get(Goal, goal_a_id) is None
    assert db_session.get(StudyLog, log_a.id) is None
    # goal_bの実績・daily_record自体は巻き添えにしない。
    assert db_session.get(DailyRecord, record_id) is not None
    assert db_session.get(StudyLog, log_b_id) is not None


def test_delete_archived_goal_with_cascade_deletes_own_diary_but_keeps_others(db_session):
    """自目標の日記（daily_goal_diary）は削除対象と道連れに消えるが、他目標の日記が
    残っている場合はdaily_record自体は保持する（データ構造編4.2、L-04関連）。
    """
    goal = _make_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT, name="削除対象")
    other_goal = _make_goal(db_session, name="他の目標")
    material = _make_material(db_session, goal.id)
    record = _make_daily_record(
        db_session, dt.date(2026, 1, 5), exam_record_state=RecordState.REPORTED
    )
    _make_study_log(db_session, record.id, material.id)
    _make_diary_entry(db_session, record.id, goal.id, diary_body="削除対象の日記")
    other_entry = _make_diary_entry(
        db_session, record.id, other_goal.id, diary_body="他の目標の日記"
    )
    record_id = record.id
    goal_service.archive_goal(db_session, goal)

    goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=True)

    assert db_session.get(DailyRecord, record_id) is not None
    assert db_session.get(DailyGoalDiary, other_entry.id) is not None
    remaining_goal_ids = {
        entry.goal_id
        for entry in db_session.query(DailyGoalDiary)
        .filter(DailyGoalDiary.daily_record_id == record_id)
        .all()
    }
    assert remaining_goal_ids == {other_goal.id}


def test_delete_archived_goal_with_cascade_deletes_daily_record_when_no_other_data_remains(
    db_session,
):
    """自目標の日記のみだった場合、study_log削除後に空になったdaily_recordは削除される
    （データ構造編4.2）。"""
    goal = _make_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    material = _make_material(db_session, goal.id)
    record = _make_daily_record(
        db_session, dt.date(2026, 1, 5), exam_record_state=RecordState.REPORTED
    )
    _make_study_log(db_session, record.id, material.id)
    _make_diary_entry(db_session, record.id, goal.id, diary_body="削除対象の日記")
    record_id = record.id
    goal_service.archive_goal(db_session, goal)

    goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=True)

    assert db_session.get(DailyRecord, record_id) is None


def test_delete_archived_goal_with_cascade_preserves_daily_record_with_chat_or_comment(
    db_session,
):
    """実績が空になってもAIチャット・コメントが残る場合はdaily_recordを保持する。"""
    goal = _make_goal(db_session, status=GoalStatus.CLOSED_WITH_RESULT)
    material = _make_material(db_session, goal.id)
    record = _make_daily_record(db_session, dt.date(2026, 1, 5))
    _make_study_log(db_session, record.id, material.id)
    db_session.add(ChatMessage(daily_record_id=record.id, role="USER", content="質問", sequence=1))
    db_session.add(RecordComment(daily_record_id=record.id, body="コメント"))
    db_session.flush()
    record_id = record.id
    goal_service.archive_goal(db_session, goal)

    goal_service.delete_archived_goal(db_session, goal, cascade_study_logs=True)

    assert db_session.get(DailyRecord, record_id) is not None
