"""完了条件: 全テーブルに対する基本的なCRUDが動作することを確認できること。

あわせて、5.1〜5.5で定義した削除時動作（CASCADE / RESTRICT）と
一意制約が実際のSQLite上で機能することを検証する
（PRAGMA foreign_keys=ON が接続ごとに有効化されていることの確認を兼ねる）。
"""

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from app.constants.enums import (
    AiPurpose,
    BaselineReason,
    ChatRole,
    ConversationScope,
    DayType,
    Environment,
    ExamDateType,
    ExamResultType,
    GoalCategory,
    GoalStatus,
    RecordState,
)
from app.models.ai import AiConversation, AiLog
from app.models.book import Book
from app.models.goal import ExamSubject, Goal, LoadProfile
from app.models.material import Material, MaterialSubject, PlanBaseline
from app.models.record import (
    ChatMessage,
    DailyMessage,
    DailyRecord,
    ExamResult,
    ReadingLog,
    RecordComment,
    StudyLog,
    WeeklySummary,
)
from app.models.resource import ResourceSlot, ResourceSlotWeekday
from app.models.retrospective import GoalRetrospective
from app.models.setting import CalendarDayOverride, Holiday


def _make_goal(name: str, start_date: dt.date) -> Goal:
    return Goal(name=name, start_date=start_date, status=GoalStatus.ACTIVE, resource_ratio=0.5)


def _make_reading_goal(name: str, start_date: dt.date) -> Goal:
    return Goal(
        name=name,
        start_date=start_date,
        status=GoalStatus.ACTIVE,
        resource_ratio=0,
        category=GoalCategory.READING,
    )


def test_goal_and_children_crud(db_session):
    goal = _make_goal("CRUD検証用資格", dt.date(2026, 1, 1))
    db_session.add(goal)
    db_session.flush()

    subject = ExamSubject(
        goal_id=goal.id,
        name="科目A",
        exam_date_type=ExamDateType.FIXED,
        exam_date_fixed=dt.date(2026, 12, 1),
        display_order=1,
    )
    material = Material(
        goal_id=goal.id,
        name="教材A",
        unit_label="問",
        total_amount=100,
        planned_cycles=2,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 11, 30),
        display_order=1,
    )
    load_profile = LoadProfile(
        goal_id=goal.id,
        date_from=dt.date(2026, 6, 1),
        date_to=dt.date(2026, 6, 30),
        coefficient=0.8,
    )
    db_session.add_all([subject, material, load_profile])
    db_session.flush()

    material_subject = MaterialSubject(material_id=material.id, subject_id=subject.id)
    plan_baseline = PlanBaseline(
        material_id=material.id,
        effective_from=dt.date(2026, 1, 1),
        baseline_daily_quota=5,
        remaining_at_baseline=200,
        plan_days_at_baseline=300,
        planned_cycles_at_baseline=2,
        reason=BaselineReason.INITIAL,
    )
    exam_result = ExamResult(
        subject_id=subject.id, taken_date=dt.date(2026, 12, 1), result=ExamResultType.PASS
    )
    db_session.add_all([material_subject, plan_baseline, exam_result])
    db_session.commit()

    assert db_session.get(Goal, goal.id).name == "CRUD検証用資格"
    assert db_session.get(Material, material.id).planned_cycles == 2
    assert db_session.get(ExamResult, exam_result.id).result == ExamResultType.PASS

    # goal をクローズ状態へ更新（Update確認）
    stored_goal = db_session.get(Goal, goal.id)
    stored_goal.status = GoalStatus.CLOSED_WITH_RESULT
    db_session.commit()
    assert db_session.get(Goal, goal.id).status == GoalStatus.CLOSED_WITH_RESULT

    # goal 削除 → exam_subject/material/load_profile/material_subject/plan_baseline/
    # exam_result がCASCADEで削除されること（study_logの参照がないため material 削除は成功する）
    db_session.delete(stored_goal)
    db_session.commit()

    assert db_session.get(Goal, goal.id) is None
    assert db_session.get(ExamSubject, subject.id) is None
    assert db_session.get(Material, material.id) is None
    assert db_session.get(LoadProfile, load_profile.id) is None
    assert db_session.get(PlanBaseline, plan_baseline.id) is None
    assert db_session.get(ExamResult, exam_result.id) is None


def test_material_delete_restricted_when_study_log_exists(db_session):
    goal = _make_goal("RESTRICT検証用資格", dt.date(2026, 2, 1))
    db_session.add(goal)
    db_session.flush()

    material = Material(
        goal_id=goal.id,
        name="実績ありの教材",
        unit_label="ページ",
        total_amount=50,
        start_date=dt.date(2026, 2, 1),
        due_date=dt.date(2026, 3, 1),
        display_order=1,
    )
    db_session.add(material)
    db_session.flush()

    daily_record = DailyRecord(
        record_date=dt.date(2026, 2, 2), exam_record_state=RecordState.REPORTED
    )
    db_session.add(daily_record)
    db_session.flush()

    study_log = StudyLog(
        daily_record_id=daily_record.id,
        material_id=material.id,
        minutes_spent=30,
        amount_completed=10,
        cycle_number=1,
    )
    db_session.add(study_log)
    db_session.commit()

    db_session.delete(material)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # 実績を消さない限り教材は削除できないことを確認したうえで、後片付けは行わない
    # （後片付けで消すと本テストの主張が薄れるため、削除不可の確認のみに留める）
    assert db_session.get(Material, material.id) is not None


def test_daily_record_and_related_records_crud(db_session):
    daily_record = DailyRecord(
        record_date=dt.date(2026, 3, 10), exam_record_state=RecordState.PROGRESS_ONLY
    )
    db_session.add(daily_record)
    db_session.flush()

    chat = ChatMessage(
        daily_record_id=daily_record.id,
        role=ChatRole.USER,
        content="今日の進捗です",
        sequence=1,
    )
    comment = RecordComment(daily_record_id=daily_record.id, body="補足コメント")
    db_session.add_all([chat, comment])
    db_session.commit()

    assert (
        db_session.get(DailyRecord, daily_record.id).exam_record_state
        == RecordState.PROGRESS_ONLY
    )
    assert len(db_session.get(DailyRecord, daily_record.id).chat_messages) == 1
    assert len(db_session.get(DailyRecord, daily_record.id).comments) == 1

    db_session.delete(db_session.get(DailyRecord, daily_record.id))
    db_session.commit()

    assert db_session.get(ChatMessage, chat.id) is None
    assert db_session.get(RecordComment, comment.id) is None


def test_daily_record_unique_record_date(db_session):
    db_session.add(
        DailyRecord(record_date=dt.date(2026, 4, 1), exam_record_state=RecordState.REPORTED)
    )
    db_session.commit()

    db_session.add(
        DailyRecord(record_date=dt.date(2026, 4, 1), exam_record_state=RecordState.REPORTED)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_resource_slot_and_weekday_crud(db_session):
    slot = ResourceSlot(
        name="朝スロット",
        start_time=dt.time(6, 0),
        end_time=dt.time(7, 0),
        environment=Environment.ANY,
        display_order=1,
    )
    db_session.add(slot)
    db_session.flush()

    db_session.add(ResourceSlotWeekday(slot_id=slot.id, weekday=0))
    db_session.commit()

    assert len(db_session.get(ResourceSlot, slot.id).weekdays) == 1

    db_session.delete(db_session.get(ResourceSlot, slot.id))
    db_session.commit()
    assert db_session.query(ResourceSlotWeekday).filter_by(slot_id=slot.id).count() == 0


def test_holiday_and_calendar_override_crud(db_session):
    holiday = Holiday(holiday_date=dt.date(2026, 1, 1), name="元日")
    override = CalendarDayOverride(
        target_date=dt.date(2026, 5, 3), day_type=DayType.OFF, note="旅行"
    )
    db_session.add_all([holiday, override])
    db_session.commit()

    assert db_session.get(Holiday, dt.date(2026, 1, 1)).name == "元日"
    assert db_session.get(CalendarDayOverride, dt.date(2026, 5, 3)).day_type == DayType.OFF


def test_weekly_summary_daily_message_retrospective_ai_conversation_ai_log_crud(db_session):
    goal = _make_goal("AI連携検証用資格", dt.date(2026, 6, 1))
    db_session.add(goal)
    db_session.flush()

    weekly_summary = WeeklySummary(
        goal_id=goal.id,
        week_start_date=dt.date(2026, 6, 1),
        week_end_date=dt.date(2026, 6, 7),
        summary_body="今週は順調に進捗した",
    )
    retrospective = GoalRetrospective(goal_id=goal.id, body="総括レポート本文")
    conversation = AiConversation(
        goal_id=goal.id,
        scope=ConversationScope.DAILY_FEEDBACK,
        scope_key="2026-06-01",
        conversation_uid="conv-uid-001",
    )
    daily_message = DailyMessage(
        target_date=dt.date(2026, 6, 1), goal_id=goal.id, body="今日も一歩前進です"
    )
    daily_message_goal_independent = DailyMessage(
        target_date=dt.date(2026, 6, 2), body="目標非依存の一言"
    )
    ai_log = AiLog(
        purpose=AiPurpose.DAILY_FEEDBACK,
        conversation_uid="conv-uid-001",
        request_body="{}",
        prompt_chars=2,
    )
    db_session.add_all(
        [
            weekly_summary,
            retrospective,
            conversation,
            daily_message,
            daily_message_goal_independent,
            ai_log,
        ]
    )
    db_session.commit()

    assert db_session.get(WeeklySummary, weekly_summary.id).goal_id == goal.id
    assert db_session.get(GoalRetrospective, retrospective.id).is_anonymized is False
    assert db_session.get(AiConversation, conversation.id).last_parent_order == 0
    assert db_session.get(DailyMessage, daily_message.id).body == "今日も一歩前進です"
    assert db_session.get(AiLog, ai_log.id).was_truncated is False

    db_session.delete(db_session.get(Goal, goal.id))
    db_session.commit()

    # goal -> weekly_summary / goal_retrospective / ai_conversation / 目標に紐づくdaily_message
    # は CASCADE（未決事項L-04: daily_messageは目標ごとに独立生成するようになったため）
    assert db_session.get(WeeklySummary, weekly_summary.id) is None
    assert db_session.get(GoalRetrospective, retrospective.id) is None
    assert db_session.get(AiConversation, conversation.id) is None
    assert db_session.get(DailyMessage, daily_message.id) is None
    # goal_id=NULL（目標非依存）のdaily_message・ai_logはgoalに紐づかないため残る
    assert db_session.get(DailyMessage, daily_message_goal_independent.id) is not None
    assert db_session.get(AiLog, ai_log.id) is not None


def test_goal_category_defaults_to_exam(db_session):
    goal = _make_goal("種別デフォルト検証用資格", dt.date(2026, 7, 1))
    db_session.add(goal)
    db_session.commit()

    assert db_session.get(Goal, goal.id).category == GoalCategory.EXAM


def test_book_and_reading_log_crud(db_session):
    goal = _make_reading_goal("読書目標CRUD検証用", dt.date(2026, 7, 1))
    db_session.add(goal)
    db_session.flush()

    book = Book(
        goal_id=goal.id,
        title="達人プログラマー",
        author="デイブトーマス",
        total_pages=350,
        start_date=dt.date(2026, 7, 1),
        due_date=dt.date(2026, 8, 31),
    )
    db_session.add(book)
    db_session.flush()

    daily_record = DailyRecord(
        record_date=dt.date(2026, 7, 2), reading_record_state=RecordState.REPORTED
    )
    db_session.add(daily_record)
    db_session.flush()

    reading_log = ReadingLog(
        daily_record_id=daily_record.id,
        book_id=book.id,
        recall_body="第1章を読んだ。DRY原則の話が印象的だった。",
        pages_read=20,
        current_page=20,
    )
    db_session.add(reading_log)
    db_session.commit()

    assert db_session.get(Book, book.id).title == "達人プログラマー"
    assert db_session.get(ReadingLog, reading_log.id).recall_body.startswith("第1章")
    assert len(db_session.get(Book, book.id).reading_logs) == 1
    # book -> reading_log は RESTRICT のため、reading_log が存在する間は goal 経由の
    # カスケード削除も成立しない（RESTRICT自体の検証はtest_book_delete_restricted_
    # when_reading_log_existsで、goal->bookのCASCADE自体の検証はreading_logの無い
    # test_book_cascade_deletes_with_goalで行う）。


def test_book_cascade_deletes_with_goal(db_session):
    goal = _make_reading_goal("goalカスケード検証用", dt.date(2026, 7, 1))
    db_session.add(goal)
    db_session.flush()

    book = Book(
        goal_id=goal.id,
        title="実績なしの書籍",
        start_date=dt.date(2026, 7, 1),
        due_date=dt.date(2026, 8, 31),
    )
    db_session.add(book)
    db_session.commit()

    # goal 削除 -> book が CASCADE で削除されること（reading_logの参照がないため成功する）
    db_session.delete(db_session.get(Goal, goal.id))
    db_session.commit()

    assert db_session.get(Goal, goal.id) is None
    assert db_session.get(Book, book.id) is None


def test_book_goal_id_unique_constraint(db_session):
    goal = _make_reading_goal("1目標1冊検証用", dt.date(2026, 7, 1))
    db_session.add(goal)
    db_session.flush()

    db_session.add(
        Book(
            goal_id=goal.id,
            title="1冊目",
            start_date=dt.date(2026, 7, 1),
            due_date=dt.date(2026, 8, 1),
        )
    )
    db_session.commit()

    db_session.add(
        Book(
            goal_id=goal.id,
            title="2冊目",
            start_date=dt.date(2026, 7, 1),
            due_date=dt.date(2026, 8, 1),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_book_delete_restricted_when_reading_log_exists(db_session):
    goal = _make_reading_goal("RESTRICT検証用読書目標", dt.date(2026, 8, 1))
    db_session.add(goal)
    db_session.flush()

    book = Book(
        goal_id=goal.id,
        title="実績ありの書籍",
        start_date=dt.date(2026, 8, 1),
        due_date=dt.date(2026, 9, 1),
    )
    db_session.add(book)
    db_session.flush()

    daily_record = DailyRecord(
        record_date=dt.date(2026, 8, 2), reading_record_state=RecordState.REPORTED
    )
    db_session.add(daily_record)
    db_session.flush()

    reading_log = ReadingLog(
        daily_record_id=daily_record.id, book_id=book.id, recall_body="想起本文"
    )
    db_session.add(reading_log)
    db_session.commit()

    db_session.delete(book)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.get(Book, book.id) is not None


def test_reading_log_unique_book_and_daily_record(db_session):
    goal = _make_reading_goal("重複防止検証用読書目標", dt.date(2026, 8, 1))
    db_session.add(goal)
    db_session.flush()

    book = Book(
        goal_id=goal.id,
        title="重複検証用書籍",
        start_date=dt.date(2026, 8, 1),
        due_date=dt.date(2026, 9, 1),
    )
    db_session.add(book)
    db_session.flush()

    daily_record = DailyRecord(
        record_date=dt.date(2026, 8, 3), reading_record_state=RecordState.REPORTED
    )
    db_session.add(daily_record)
    db_session.flush()

    db_session.add(
        ReadingLog(daily_record_id=daily_record.id, book_id=book.id, recall_body="1件目")
    )
    db_session.commit()

    db_session.add(
        ReadingLog(daily_record_id=daily_record.id, book_id=book.id, recall_body="2件目")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
