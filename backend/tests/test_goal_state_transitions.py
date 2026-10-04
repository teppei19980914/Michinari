"""目標の状態遷移・削除・記録の制限の全組み合わせテスト（開発Todo 5-1、1-1〜1-7、不具合A〜C）。

状態（下書き・実行中・一時停止・中断・完了）× 操作 × 種類を表形式で固定する。許可された遷移は
成功し、それ以外は必ず拒否されることを確かめる。遷移表そのもの（constants/goal_transitions.py）は
ここで設計資料の表と突き合わせて固定する。
"""

import datetime as dt

import pytest

from app.constants.enums import GoalCategory, GoalStatus
from app.constants.goal_transitions import (
    RESUME_WARNING_QUOTA_INCREASED,
    GoalOperation,
    is_operation_allowed,
)
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, WorkLog
from app.models.work import WorkAssignment, WorkEvaluationReport, WorkMember
from app.services import (
    goal_service,
    record_service,
    retrospective_service,
)
from app.services.exceptions import (
    ExamResultsIncompleteError,
    InvalidStateTransitionError,
    ValidationError,
)
from app.services.record_service import (
    DiaryEntryItem,
    StudyLogItem,
    WorkLogItem,
)
from tests import reading_helpers
from tests.diary_helpers import make_exam_goal

TODAY = dt.date(2026, 3, 10)

ST = GoalStatus
OP = GoalOperation

#: 設計資料 1-1 の遷移表（期待値の正本。遷移表を変えたらここも変える＝仕様変更の記録）。
EXPECTED_ALLOWED: dict[GoalOperation, set[GoalStatus]] = {
    OP.ACTIVATE: {ST.DRAFT},
    OP.PAUSE: {ST.ACTIVE},
    OP.RESUME: {ST.PAUSED, ST.CLOSED_WITHOUT_RESULT, ST.CLOSED_WITH_RESULT},
    OP.ABANDON: {ST.ACTIVE, ST.PAUSED},
    OP.COMPLETE: {ST.ACTIVE},
    OP.RECORD: {ST.ACTIVE},
    OP.ARCHIVE: {ST.DRAFT, ST.PAUSED, ST.CLOSED_WITHOUT_RESULT, ST.CLOSED_WITH_RESULT},
    OP.DELETE: {ST.DRAFT, ST.PAUSED, ST.CLOSED_WITHOUT_RESULT, ST.CLOSED_WITH_RESULT},
    OP.UNARCHIVE: set(ST),
}


@pytest.mark.parametrize("operation", list(GoalOperation))
def test_transition_table_matches_the_design(operation):
    """遷移表が設計資料 1-1 と一致する（全状態について許可・禁止を固定）。"""
    for status in GoalStatus:
        assert is_operation_allowed(operation, status) == (status in EXPECTED_ALLOWED[operation]), (
            operation,
            status,
        )


def test_forbidden_transitions_named_in_the_design_are_rejected():
    """設計資料 1-1 の禁止遷移の一覧（実行中→アーカイブ、一時停止→完了、完了⇄中断、中断→完了、
    実行中→削除）が、遷移表で許可されていないこと。"""
    assert not is_operation_allowed(OP.ARCHIVE, ST.ACTIVE)
    assert not is_operation_allowed(OP.COMPLETE, ST.PAUSED)
    assert not is_operation_allowed(OP.COMPLETE, ST.CLOSED_WITHOUT_RESULT)
    assert not is_operation_allowed(OP.ABANDON, ST.CLOSED_WITH_RESULT)
    assert not is_operation_allowed(OP.ABANDON, ST.CLOSED_WITHOUT_RESULT)
    assert not is_operation_allowed(OP.DELETE, ST.ACTIVE)


def _make_goal_in(session, category: GoalCategory, status: GoalStatus) -> Goal:
    """指定の種類・状態の目標を作る。書籍は下書きの間に作り、その後で状態だけを置く
    （クローズ済みの目標は書籍を追加できないため）。"""
    if category == GoalCategory.READING:
        goal = reading_helpers.make_reading_goal(session, status=GoalStatus.DRAFT)
        reading_helpers.make_book(session, goal.id)
    elif category == GoalCategory.WORK:
        goal = Goal(
            category=GoalCategory.WORK,
            name="仕事目標A",
            start_date=dt.date(2026, 1, 1),
            status=GoalStatus.DRAFT,
        )
        session.add(goal)
        session.flush()
        goal.work_assignment = WorkAssignment(expected_content="想定業務", start_date=TODAY)
        session.flush()
    else:
        goal = make_exam_goal(session, status=GoalStatus.DRAFT)
    goal.status = status
    session.flush()
    return goal


# --- 状態×操作の表（許可された遷移は成功し、それ以外は拒否される） ---

_SERVICE_ACTIONS = {
    OP.PAUSE: lambda s, g: goal_service.pause_goal(s, g),
    OP.ABANDON: lambda s, g: goal_service.abandon_goal(s, g),
    OP.RESUME: lambda s, g: goal_service.resume_goal(s, g),
    OP.COMPLETE: lambda s, g: goal_service.complete_goal(s, g),
    OP.ARCHIVE: lambda s, g: goal_service.archive_goal(s, g),
    OP.DELETE: lambda s, g: goal_service.delete_goal(s, g),
}


@pytest.mark.parametrize("category", [GoalCategory.READING, GoalCategory.WORK])
@pytest.mark.parametrize("operation", list(_SERVICE_ACTIONS))
@pytest.mark.parametrize("status", list(GoalStatus))
def test_service_operation_follows_the_transition_table(
    seeded_session, category, operation, status
):
    goal = _make_goal_in(seeded_session, category, status)
    goal_id = goal.id
    action = _SERVICE_ACTIONS[operation]

    if status in EXPECTED_ALLOWED[operation]:
        action(seeded_session, goal)
        if operation == OP.DELETE:
            assert seeded_session.get(Goal, goal_id) is None
        elif operation == OP.ARCHIVE:
            assert goal.archived_at is not None
        else:
            assert goal.status == _EXPECTED_RESULT_STATUS[operation]
    else:
        with pytest.raises(InvalidStateTransitionError):
            action(seeded_session, goal)


_EXPECTED_RESULT_STATUS = {
    OP.PAUSE: GoalStatus.PAUSED,
    OP.ABANDON: GoalStatus.CLOSED_WITHOUT_RESULT,
    OP.RESUME: GoalStatus.ACTIVE,
    OP.COMPLETE: GoalStatus.CLOSED_WITH_RESULT,
}


def test_resume_from_closed_clears_closed_at_and_keeps_the_data(seeded_session):
    """中断・完了からの再開では、データを引き継ぎ、終了時刻を解除する（開発Todo 1-5）。"""
    goal = _make_goal_in(seeded_session, GoalCategory.READING, GoalStatus.CLOSED_WITHOUT_RESULT)
    goal.closed_at = dt.datetime(2026, 2, 1)
    book_id = goal.book.id

    goal_service.resume_goal(seeded_session, goal)

    assert goal.status == GoalStatus.ACTIVE
    assert goal.closed_at is None
    assert goal.start_date == dt.date(2026, 1, 1)  # 開始日は変更しない
    assert goal.book.id == book_id


def test_resume_from_archived_goal_is_rejected(seeded_session):
    goal = _make_goal_in(seeded_session, GoalCategory.READING, GoalStatus.PAUSED)
    goal_service.archive_goal(seeded_session, goal)

    with pytest.raises(InvalidStateTransitionError):
        goal_service.resume_goal(seeded_session, goal)


def test_complete_exam_goal_requires_all_results(seeded_session):
    goal = make_exam_goal(seeded_session, status=GoalStatus.ACTIVE)

    with pytest.raises(ExamResultsIncompleteError):
        goal_service.complete_goal(seeded_session, goal)


def test_complete_reading_goal_requires_a_book(seeded_session):
    goal = reading_helpers.make_reading_goal(seeded_session, status=GoalStatus.ACTIVE)

    with pytest.raises(ValidationError):
        goal_service.complete_goal(seeded_session, goal)


def test_complete_work_goal_requires_an_assignment(seeded_session):
    goal = Goal(
        category=GoalCategory.WORK,
        name="仕事目標A",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    seeded_session.add(goal)
    seeded_session.flush()

    with pytest.raises(ValidationError):
        goal_service.complete_goal(seeded_session, goal)


def test_delete_work_goal_cascades_evaluation_reports(seeded_session):
    """評価レポートがある仕事目標も削除できる。レポートとメンバーは一緒に消える（不具合C）。"""
    goal = _make_goal_in(seeded_session, GoalCategory.WORK, GoalStatus.DRAFT)
    assignment = goal.work_assignment
    member = WorkMember(work_assignment_id=assignment.id, name="メンバーA", is_active=True)
    seeded_session.add(member)
    seeded_session.flush()
    report = WorkEvaluationReport(
        work_assignment_id=assignment.id,
        member_id=member.id,
        considerations="",
        body="評価本文",
        generated_at=dt.datetime(2026, 2, 1),
    )
    seeded_session.add(report)
    seeded_session.flush()
    goal_id = goal.id

    goal_service.delete_goal(seeded_session, goal)

    assert seeded_session.get(Goal, goal_id) is None
    assert seeded_session.query(WorkEvaluationReport).count() == 0
    assert seeded_session.query(WorkMember).count() == 0


def test_delete_goal_keeps_daily_record_that_still_has_other_goal_data(seeded_session):
    """カスケード削除でも、同日に他目標のデータが残る日次報告は残す（R-63）。"""
    goal = _make_goal_in(seeded_session, GoalCategory.WORK, GoalStatus.DRAFT)
    other = _make_goal_in(seeded_session, GoalCategory.WORK, GoalStatus.DRAFT)
    other.work_assignment.expected_content = "別の案件"
    record = DailyRecord(record_date=TODAY, work_record_state="PROGRESS_ONLY")
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        WorkLog(daily_record_id=record.id, work_assignment_id=goal.work_assignment.id, body="a")
    )
    seeded_session.add(
        WorkLog(daily_record_id=record.id, work_assignment_id=other.work_assignment.id, body="b")
    )
    seeded_session.flush()
    record_id = record.id

    goal_service.delete_goal(seeded_session, goal)

    assert seeded_session.get(DailyRecord, record_id) is not None
    assert seeded_session.query(WorkLog).count() == 1


# --- 記録の制限（不具合A）：実行中の目標以外には実績・日記・コメントを登録できない ---


def _make_material(session, goal: Goal) -> Material:
    from app.constants.enums import Environment, QualityMetricType
    from app.services import material_service, subject_service

    subject = subject_service.create_subject(
        session,
        goal,
        name="科目A",
        exam_date_type=_exam_date_type_fixed(),
        exam_date_from=None,
        exam_date_to=None,
        exam_date_fixed=dt.date(2026, 6, 1),
        passing_score=None,
    )
    return material_service.create_material(
        session,
        goal,
        name="教材A",
        unit_label="ページ",
        total_amount=100,
        planned_cycles=1,
        subject_ids=[subject.id],
        start_date=dt.date(2026, 1, 1),
        due_date=None,
        due_date_is_manual=False,
        required_block_minutes=None,
        required_environment=Environment.ANY,
        quality_metric_type=QualityMetricType.NONE,
    )


def _exam_date_type_fixed():
    from app.constants.enums import ExamDateType

    return ExamDateType.FIXED


@pytest.mark.parametrize(
    "status",
    [
        GoalStatus.DRAFT,
        GoalStatus.PAUSED,
        GoalStatus.CLOSED_WITHOUT_RESULT,
        GoalStatus.CLOSED_WITH_RESULT,
    ],
)
def test_study_log_is_rejected_unless_goal_is_active(seeded_session, status):
    goal = make_exam_goal(seeded_session, status=GoalStatus.ACTIVE)
    material = _make_material(seeded_session, goal)
    goal.status = status
    seeded_session.flush()

    with pytest.raises(InvalidStateTransitionError):
        record_service.register_progress(
            seeded_session,
            TODAY,
            [
                StudyLogItem(
                    material_id=material.id,
                    slot_minutes={},
                    amount_completed=1,
                    cycle_number=1,
                    quality_value=None,
                )
            ],
            TODAY,
        )


@pytest.mark.parametrize("status", [GoalStatus.PAUSED, GoalStatus.CLOSED_WITHOUT_RESULT])
def test_reading_log_is_rejected_unless_goal_is_active(seeded_session, status):
    goal = reading_helpers.make_reading_goal(seeded_session, status=GoalStatus.DRAFT)
    book = reading_helpers.make_book(seeded_session, goal.id)
    goal.status = status
    seeded_session.flush()

    with pytest.raises(InvalidStateTransitionError):
        record_service.register_progress(
            seeded_session,
            TODAY,
            [],
            TODAY,
            reading_items=[reading_helpers.reading_log_item(book.id)],
        )


@pytest.mark.parametrize("status", [GoalStatus.PAUSED, GoalStatus.CLOSED_WITH_RESULT])
def test_work_log_is_rejected_unless_goal_is_active(seeded_session, status):
    goal = _make_goal_in(seeded_session, GoalCategory.WORK, status)

    with pytest.raises(InvalidStateTransitionError):
        record_service.register_progress(
            seeded_session,
            TODAY,
            [],
            TODAY,
            work_items=[WorkLogItem(work_assignment_id=goal.work_assignment.id, body="業務")],
        )


@pytest.mark.parametrize("status", [GoalStatus.PAUSED, GoalStatus.CLOSED_WITHOUT_RESULT])
def test_diary_is_rejected_unless_goal_is_active(seeded_session, status):
    goal = make_exam_goal(seeded_session, status=status)

    with pytest.raises(InvalidStateTransitionError):
        record_service.finalize_record(
            seeded_session,
            TODAY,
            [],
            [DiaryEntryItem(goal_id=goal.id, diary_body="日記", diary_learned="学び")],
            TODAY,
        )


def test_active_goal_still_accepts_records(seeded_session):
    goal = make_exam_goal(seeded_session, status=GoalStatus.ACTIVE)
    material = _make_material(seeded_session, goal)

    record = record_service.register_progress(
        seeded_session,
        TODAY,
        [
            StudyLogItem(
                material_id=material.id,
                slot_minutes={},
                amount_completed=1,
                cycle_number=1,
                quality_value=None,
            )
        ],
        TODAY,
    )
    assert record.study_logs


def test_comment_requires_at_least_one_active_goal(seeded_session):
    """コメントは実行中の目標が存在する間のみ操作できる（開発Todo 1-7、未決事項の既定値）。"""
    make_exam_goal(seeded_session, status=GoalStatus.PAUSED)
    seeded_session.add(DailyRecord(record_date=TODAY, exam_record_state="REPORTED"))
    seeded_session.flush()

    with pytest.raises(InvalidStateTransitionError):
        record_service.add_comment(seeded_session, TODAY, "コメント")

    make_exam_goal(seeded_session, name="実行中", status=GoalStatus.ACTIVE)
    comment = record_service.add_comment(seeded_session, TODAY, "コメント")
    assert comment.body == "コメント"


# --- 読了レポートの制限（不具合B） ---


@pytest.mark.parametrize(
    "status", [GoalStatus.ACTIVE, GoalStatus.PAUSED, GoalStatus.CLOSED_WITHOUT_RESULT]
)
def test_reading_retrospective_requires_a_completed_goal(seeded_session, status):
    goal = reading_helpers.make_reading_goal(seeded_session, status=GoalStatus.DRAFT)
    reading_helpers.make_book(seeded_session, goal.id)
    goal.status = status
    seeded_session.flush()

    with pytest.raises(InvalidStateTransitionError):
        retrospective_service.generate_retrospective(seeded_session, goal, today=TODAY)


def test_reading_retrospective_without_book_on_completed_goal_is_rejected(seeded_session):
    goal = reading_helpers.make_reading_goal(seeded_session, status=GoalStatus.CLOSED_WITH_RESULT)

    with pytest.raises(ValidationError):
        retrospective_service.generate_retrospective(seeded_session, goal, today=TODAY)


# --- 状態遷移履歴と再開日（開発Todo 1-5・1-6、P2） ---


def test_status_history_records_each_transition_and_skips_rejected_ones(seeded_session):
    """作成・開始・一時停止・再開・中断の各遷移が1行ずつ残る。拒否された遷移は残らない。"""
    from app.models.goal import GoalStatusHistory

    goal = goal_service.create_goal(
        seeded_session,
        name="読書履歴",
        start_date=dt.date(2026, 1, 1),
        memo=None,
        category=GoalCategory.READING,
    )
    reading_helpers.make_book(seeded_session, goal.id)
    goal_service.activate_goal(seeded_session, goal)
    goal_service.pause_goal(seeded_session, goal)
    goal_service.resume_goal(seeded_session, goal)
    goal_service.abandon_goal(seeded_session, goal)
    with pytest.raises(InvalidStateTransitionError):
        goal_service.complete_goal(seeded_session, goal)

    rows = (
        seeded_session.query(GoalStatusHistory)
        .filter(GoalStatusHistory.goal_id == goal.id)
        .order_by(GoalStatusHistory.id)
        .all()
    )
    assert [(row.from_status, row.to_status) for row in rows] == [
        (None, GoalStatus.DRAFT),
        (GoalStatus.DRAFT, GoalStatus.ACTIVE),
        (GoalStatus.ACTIVE, GoalStatus.PAUSED),
        (GoalStatus.PAUSED, GoalStatus.ACTIVE),
        (GoalStatus.ACTIVE, GoalStatus.CLOSED_WITHOUT_RESULT),
    ]


def test_resume_stamps_the_resume_date_and_keeps_the_start_date(seeded_session):
    goal = reading_helpers.make_reading_goal(
        seeded_session, status=GoalStatus.CLOSED_WITHOUT_RESULT
    )
    reading_helpers.make_book(seeded_session, goal.id)
    assert goal.resumed_at is None

    result = goal_service.resume_goal(seeded_session, goal)

    assert result.goal.resumed_at is not None
    assert result.goal.start_date == dt.date(2026, 1, 1)
    assert result.warnings == []


@pytest.fixture
def exam_goal_with_material(seeded_session, monkeypatch):
    """資格試験の目標（一時停止中・教材あり）。資源配分の検証は本テストの対象外のため通す。"""
    goal = make_exam_goal(seeded_session, status=GoalStatus.ACTIVE)
    _make_material(seeded_session, goal)
    goal.status = GoalStatus.PAUSED
    seeded_session.flush()
    monkeypatch.setattr(goal_service.allocation_service, "sum_allocated_minutes", lambda s, gid: 60)
    monkeypatch.setattr(goal_service, "_validate_allocation_capacity", lambda s, g: None)
    return goal


def _stub_baselines(monkeypatch, *, previous_quota, new_quota):
    """停止前の基準値と、再開時に再記録される基準値を差し替える（閾値判定の検証用）。"""
    from types import SimpleNamespace

    from app.services import baseline_service

    recorded_reasons = []
    monkeypatch.setattr(
        baseline_service,
        "get_current_baseline",
        lambda s, material_id, today: SimpleNamespace(baseline_daily_quota=previous_quota),
    )

    def _record(s, material, reason, today, treat):
        recorded_reasons.append(reason)
        return SimpleNamespace(baseline_daily_quota=new_quota)

    monkeypatch.setattr(goal_service, "record_baseline_for_material", _record)
    return recorded_reasons


def test_resume_exam_goal_replans_with_reason_resumed_and_warns_when_quota_jumps(
    seeded_session, monkeypatch, exam_goal_with_material
):
    from app.constants.enums import BaselineReason

    reasons = _stub_baselines(monkeypatch, previous_quota=1.0, new_quota=2.0)

    result = goal_service.resume_goal(seeded_session, exam_goal_with_material)

    assert reasons == [BaselineReason.RESUMED]
    assert result.warnings == [RESUME_WARNING_QUOTA_INCREASED]
    assert exam_goal_with_material.status == GoalStatus.ACTIVE


def test_resume_exam_goal_does_not_warn_when_quota_stays_within_the_ratio(
    seeded_session, monkeypatch, exam_goal_with_material
):
    _stub_baselines(monkeypatch, previous_quota=1.0, new_quota=1.2)

    result = goal_service.resume_goal(seeded_session, exam_goal_with_material)

    assert result.warnings == []


def test_resume_exam_goal_without_previous_baseline_does_not_warn(
    seeded_session, monkeypatch, exam_goal_with_material
):
    from app.services import baseline_service

    monkeypatch.setattr(baseline_service, "get_current_baseline", lambda s, mid, today: None)
    monkeypatch.setattr(
        goal_service,
        "record_baseline_for_material",
        lambda s, material, reason, today, treat: type("B", (), {"baseline_daily_quota": 9.0})(),
    )

    result = goal_service.resume_goal(seeded_session, exam_goal_with_material)

    assert result.warnings == []


def test_resume_exam_goal_skips_inactive_materials_when_replanning(
    seeded_session, monkeypatch, exam_goal_with_material
):
    """無効化された教材（終了済みの教材）は再計画の対象外（基準値を新たに記録しない）。"""
    for material in exam_goal_with_material.materials:
        material.is_active = False
    seeded_session.flush()
    reasons = _stub_baselines(monkeypatch, previous_quota=1.0, new_quota=9.0)

    result = goal_service.resume_goal(seeded_session, exam_goal_with_material)

    assert reasons == []
    assert result.warnings == []
