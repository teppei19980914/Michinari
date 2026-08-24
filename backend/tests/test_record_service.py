"""record_service のテスト（設計書データ構造編5.4・6.2、仕様書6.4〜6.7・7.2・14章、
実装フェーズ分割計画書Phase4）。

today はサービス層の引数として明示的に渡す設計のため、システム時刻に依存せず
決定論的にテストできる（呼び出し側=API層がgoal_service.resolve_todayで算出する）。
"""

import datetime as dt

import pytest

from app.constants.enums import GoalStatus, QualityMetricType, RecordState
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, RecordComment
from app.services import cycle_service, record_service
from app.services.exceptions import (
    BackdateLimitExceededError,
    ImmutableRecordError,
    NotFoundError,
    ValidationError,
)
from app.services.record_service import StudyLogItem


def _make_goal(session, status=GoalStatus.ACTIVE):
    goal = Goal(name="目標A", start_date=dt.date(2026, 1, 1), status=status)
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
        material_id=material_id, minutes_spent=30, amount_completed=10, cycle_number=1,
        quality_value=None,
    )
    defaults.update(overrides)
    return StudyLogItem(**defaults)


# --- register_progress ---


def test_register_progress_creates_record_and_study_log(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service.register_progress(
        seeded_session, today, [_log(material.id, cycle_number=None)], today
    )

    assert record.record_state == RecordState.PROGRESS_ONLY
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
    assert record.record_state == RecordState.PROGRESS_ONLY


def test_register_progress_rejects_update_to_reported_record(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)
    seeded_session.add(DailyRecord(record_date=today, record_state=RecordState.REPORTED))
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


def test_register_progress_rejects_unknown_material(seeded_session):
    today = dt.date(2026, 3, 10)

    with pytest.raises(NotFoundError):
        record_service.register_progress(seeded_session, today, [_log(9999)], today)


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
        seeded_session, today, [_log(material.id)], "今日はよく頑張った", "過去問を解いた", today
    )

    assert record.record_state == RecordState.REPORTED
    assert record.reported_at is not None
    assert record.diary_body == "今日はよく頑張った"
    assert record.diary_learned == "過去問を解いた"


def test_finalize_record_allows_yesterday(seeded_session):
    """『前日』の判定はtoday引数を基準とし、境界値『当日または前日』を満たすこと（仕様書7.2）。"""
    today = dt.date(2026, 3, 10)
    yesterday = today - dt.timedelta(days=1)

    record = record_service.finalize_record(seeded_session, yesterday, [], "所感", "学び", today)
    assert record.record_state == RecordState.REPORTED


def test_finalize_record_rejects_two_days_ago(seeded_session):
    today = dt.date(2026, 3, 10)
    two_days_ago = today - dt.timedelta(days=2)

    with pytest.raises(BackdateLimitExceededError):
        record_service.finalize_record(seeded_session, two_days_ago, [], "所感", "学び", today)


def test_finalize_record_rejects_future_date(seeded_session):
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service.finalize_record(
            seeded_session, today + dt.timedelta(days=1), [], "所感", "学び", today
        )


def test_finalize_record_rejects_already_reported(seeded_session):
    today = dt.date(2026, 3, 10)
    seeded_session.add(DailyRecord(record_date=today, record_state=RecordState.REPORTED))
    seeded_session.flush()

    with pytest.raises(ImmutableRecordError):
        record_service.finalize_record(seeded_session, today, [], "所感", "学び", today)


def test_finalize_record_promotes_progress_only_record(seeded_session):
    """進捗のみ登録済→報告済への昇格（仕様書7.2の状態遷移）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record_service.register_progress(seeded_session, today, [_log(material.id)], today)
    record = record_service.finalize_record(seeded_session, today, [], "所感", "学び", today)

    assert record.record_state == RecordState.REPORTED
    assert len(record.study_logs) == 1  # 進捗のみ登録時点のstudy_logが保持される


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
    seeded_session.add(DailyRecord(record_date=today, record_state=RecordState.REPORTED))
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


def test_compute_daily_quota_excludes_past_due_material(seeded_session):
    goal = _make_goal(seeded_session, status=GoalStatus.ACTIVE)
    _make_material(seeded_session, goal, due_date=dt.date(2026, 3, 1))

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
        DailyRecord(record_date=dt.date(2026, 3, 10), record_state=RecordState.REPORTED)
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


def test_get_calendar_days_returns_empty_when_range_inverted(seeded_session):
    """境界値: 期間が逆転している場合に例外が発生しないこと（Phase2完了条件の踏襲）。"""
    days = record_service.get_calendar_days(
        seeded_session, dt.date(2026, 3, 10), dt.date(2026, 3, 1)
    )
    assert days == []
