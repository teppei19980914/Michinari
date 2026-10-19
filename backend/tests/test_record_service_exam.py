"""record_service_exam のテスト（設計書データ構造編5.4・6.2、仕様書6.4〜6.7・7.2・14章、
実装フェーズ分割計画書Phase4・S02）。共通処理・カテゴリ横断の相互独立性のテストは
test_record_service_common.pyを参照（実装フェーズ分割計画書S02、test_record_service.py
からの分割）。

today はサービス層の引数として明示的に渡す設計のため、システム時刻に依存せず
決定論的にテストできる（呼び出し側=API層がgoal_service.resolve_todayで算出する）。
"""

import datetime as dt

import pytest

from app.constants.enums import Environment, GoalStatus, QualityMetricType, RecordState
from app.models.material import Material
from app.models.record import DailyRecord, WeeklySummary
from app.models.resource import ResourceSlot
from app.services import cycle_service, record_service_common, record_service_exam
from app.services.exceptions import (
    BackdateLimitExceededError,
    ImmutableRecordError,
    NotFoundError,
    ValidationError,
)
from app.services.record_service_exam import StudyLogItem
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


def _make_slot(session) -> ResourceSlot:
    """時間枠を1件用意する。

    投下時間は時間枠ごとに入力する仕様（仕様書6.5）になったため、実績の登録には登録済みの
    時間枠が必要になる。
    """
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


# --- register_progress（資格試験分） ---


def test_register_progress_creates_record_and_study_log(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
        seeded_session, today, [_log(material.id, cycle_number=None)], today
    )

    assert record.exam_record_state == RecordState.PROGRESS_ONLY
    assert len(record.study_logs) == 1
    assert record.study_logs[0].cycle_number == 1  # 既定値=算出された現在周回（Phase4完了条件）


def test_register_progress_updates_existing_study_log_for_same_material(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    slot = _make_slot(seeded_session)

    record_service_common.register_progress(seeded_session, today, [_log(material.id)], today)
    record = record_service_common.register_progress(
        seeded_session,
        today,
        [_log(material.id, slot_minutes={slot.id: 45}, amount_completed=15)],
        today,
    )

    assert len(record.study_logs) == 1
    assert record.study_logs[0].amount_completed == 15
    assert record.study_logs[0].minutes_spent == 45
    slot_times = record.study_logs[0].slot_times
    assert [(row.slot_id, row.minutes) for row in slot_times] == [(slot.id, 45)]


def test_register_progress_rejects_unknown_material(seeded_session):
    today = dt.date(2026, 3, 10)

    with pytest.raises(NotFoundError):
        record_service_common.register_progress(seeded_session, today, [_log(9999)], today)


def test_finalize_record_rejects_unknown_goal_in_diary_entry(seeded_session):
    today = dt.date(2026, 3, 10)

    with pytest.raises(NotFoundError):
        record_service_exam.finalize_record(seeded_session, today, [], [_diary(9999)], today)


def test_finalize_record_duplicate_goal_in_diary_entries_last_one_wins(seeded_session):
    """同一goal_idの日記エントリが複数渡された場合、後勝ちで1件に更新される。"""
    goal = _make_goal(seeded_session)
    today = dt.date(2026, 3, 10)

    record = record_service_exam.finalize_record(
        seeded_session,
        today,
        [],
        [_diary(goal.id, "1件目", "学び1"), _diary(goal.id, "2件目", "学び2")],
        today,
    )

    entries = record_service_exam.get_diary_entries(seeded_session, record)
    assert len(entries) == 1
    assert entries[0].diary_body == "2件目"


def test_register_progress_time_not_entered_is_excluded_from_speed_by_design(seeded_session):
    """時間枠の入力が1件も無くても登録自体は成立し、投下時間はNULL（0ではない）となる
    （実効速度算出からの除外はspeed_service側の責務、ロジック・プロンプト編8.4）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
        seeded_session, today, [_log(material.id, slot_minutes={})], today
    )
    assert record.study_logs[0].minutes_spent is None
    assert record.study_logs[0].slot_times == []


def test_register_progress_cycle_number_override_is_respected(seeded_session):
    """周回番号の既定値は算出値だが、利用者が明示指定した値で上書きできる（Phase4完了条件）。

    total_amount=10・planned_cycles=2の教材で1周目(10)を完了させると、既定値としての
    現在周回は2に進む。この状態で2件目のstudy_logにcycle_number=1を明示指定すると、
    既定値(2)ではなく指定値(1)が保存されることを検証する。
    """
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, total_amount=10.0, planned_cycles=2)
    today = dt.date(2026, 3, 10)

    record_service_common.register_progress(
        seeded_session, today, [_log(material.id, amount_completed=10, cycle_number=None)], today
    )
    assert cycle_service.get_material_progress(seeded_session, material).current_cycle == 2

    tomorrow = today + dt.timedelta(days=1)
    record = record_service_common.register_progress(
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
        record_service_common.register_progress(
            seeded_session, today, [_log(material.id, quality_value=3.5)], today
        )


# --- finalize_record ---


def test_finalize_record_marks_reported_and_sets_diary(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record = record_service_exam.finalize_record(
        seeded_session,
        today,
        [_log(material.id)],
        [_diary(goal.id, "今日はよく頑張った", "過去問を解いた")],
        today,
    )

    assert record.exam_record_state == RecordState.REPORTED
    assert record.exam_reported_at is not None
    entries = record_service_exam.get_diary_entries(seeded_session, record)
    assert len(entries) == 1
    assert entries[0].goal_id == goal.id
    assert entries[0].diary_body == "今日はよく頑張った"
    assert entries[0].diary_learned == "過去問を解いた"


def test_finalize_record_allows_yesterday(seeded_session):
    """『前日』の判定はtoday引数を基準とし、境界値『当日または前日』を満たすこと（仕様書7.2）。"""
    today = dt.date(2026, 3, 10)
    yesterday = today - dt.timedelta(days=1)

    record = record_service_exam.finalize_record(seeded_session, yesterday, [], [], today)
    assert record.exam_record_state == RecordState.REPORTED


def test_finalize_record_rejects_two_days_ago(seeded_session):
    today = dt.date(2026, 3, 10)
    two_days_ago = today - dt.timedelta(days=2)

    with pytest.raises(BackdateLimitExceededError):
        record_service_exam.finalize_record(seeded_session, two_days_ago, [], [], today)


def test_finalize_record_rejects_future_date(seeded_session):
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service_exam.finalize_record(
            seeded_session, today + dt.timedelta(days=1), [], [], today
        )


def test_finalize_record_rejects_already_reported(seeded_session):
    today = dt.date(2026, 3, 10)
    seeded_session.add(DailyRecord(record_date=today, exam_record_state=RecordState.REPORTED))
    seeded_session.flush()

    with pytest.raises(ImmutableRecordError):
        record_service_exam.finalize_record(seeded_session, today, [], [], today)


def test_finalize_record_promotes_progress_only_record(seeded_session):
    """進捗のみ登録済→報告済への昇格（仕様書7.2の状態遷移）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    record_service_common.register_progress(seeded_session, today, [_log(material.id)], today)
    record = record_service_exam.finalize_record(seeded_session, today, [], [], today)

    assert record.exam_record_state == RecordState.REPORTED
    assert len(record.study_logs) == 1  # 進捗のみ登録時点のstudy_logが保持される


# --- 品質指標の正規化（ロジック・プロンプト編14.1） ---


def test_subjective_quality_is_normalized(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(
        seeded_session, goal, quality_metric_type=QualityMetricType.SUBJECTIVE
    )
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
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
        record_service_common.register_progress(
            seeded_session, today, [_log(material.id, quality_value=6)], today
        )


def test_objective_quality_passes_through(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, quality_metric_type=QualityMetricType.OBJECTIVE)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
        seeded_session, today, [_log(material.id, quality_value=72.5)], today
    )
    assert record.study_logs[0].quality_value == 72.5


def test_objective_quality_rejects_out_of_range(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, quality_metric_type=QualityMetricType.OBJECTIVE)
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service_common.register_progress(
            seeded_session, today, [_log(material.id, quality_value=150)], today
        )


def test_quality_rejects_value_when_metric_type_is_none(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal, quality_metric_type=QualityMetricType.NONE)
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service_common.register_progress(
            seeded_session, today, [_log(material.id, quality_value=50)], today
        )


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

    items = record_service_exam.compute_daily_quota(seeded_session, target_date)

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

    items = record_service_exam.compute_daily_quota(seeded_session, target_date)

    items_by_material = {item.material_id: item for item in items}
    assert items_by_material[material_a.id].goal_id == goal_a.id
    assert items_by_material[material_a.id].goal_name == "目標A"
    assert items_by_material[material_b.id].goal_id == goal_b.id
    assert items_by_material[material_b.id].goal_name == "目標B"


def test_compute_daily_quota_excludes_past_due_material(seeded_session):
    goal = _make_goal(seeded_session, status=GoalStatus.ACTIVE)
    _make_material(seeded_session, goal, due_date=dt.date(2026, 3, 1))

    items = record_service_exam.compute_daily_quota(seeded_session, dt.date(2026, 3, 10))
    assert items == []


def test_compute_daily_quota_excludes_material_before_start_date(seeded_session):
    goal = _make_goal(seeded_session, status=GoalStatus.ACTIVE)
    _make_material(
        seeded_session,
        goal,
        start_date=dt.date(2026, 4, 1),
        due_date=dt.date(2026, 12, 31),
    )

    items = record_service_exam.compute_daily_quota(seeded_session, dt.date(2026, 3, 10))
    assert items == []


def test_compute_daily_quota_excludes_inactive_goal(seeded_session):
    goal = _make_goal(seeded_session, status=GoalStatus.PAUSED)
    _make_material(seeded_session, goal, due_date=dt.date(2026, 12, 31))

    items = record_service_exam.compute_daily_quota(seeded_session, dt.date(2026, 3, 10))
    assert items == []


def test_compute_daily_quota_excludes_inactive_material(seeded_session):
    goal = _make_goal(seeded_session, status=GoalStatus.ACTIVE)
    _make_material(seeded_session, goal, due_date=dt.date(2026, 12, 31), is_active=False)

    items = record_service_exam.compute_daily_quota(seeded_session, dt.date(2026, 3, 10))
    assert items == []


# --- 前回の記録（記録画面改善タスク2026-09-17、get_previous_diary_entry） ---


def test_get_previous_diary_entry_returns_most_recent_before_target_date(seeded_session):
    goal = _make_goal(seeded_session)
    record_service_exam.finalize_record(
        seeded_session, dt.date(2026, 3, 8), [], [_diary(goal.id, "3/8の所感")], dt.date(2026, 3, 8)
    )
    record_service_exam.finalize_record(
        seeded_session, dt.date(2026, 3, 9), [], [_diary(goal.id, "3/9の所感")], dt.date(2026, 3, 9)
    )

    entry = record_service_exam.get_previous_diary_entry(
        seeded_session, goal.id, dt.date(2026, 3, 10)
    )

    assert entry.record_date == dt.date(2026, 3, 9)
    assert entry.body == "3/9の所感"


def test_get_previous_diary_entry_excludes_entry_on_target_date(seeded_session):
    """対象日「より前」のみが対象（同日は「前回」ではなく「今回」のため除外する）。"""
    goal = _make_goal(seeded_session)
    target = dt.date(2026, 3, 10)
    record_service_exam.finalize_record(
        seeded_session, target, [], [_diary(goal.id, "当日の所感")], target
    )

    entry = record_service_exam.get_previous_diary_entry(seeded_session, goal.id, target)

    assert entry is None


def test_get_previous_diary_entry_skips_empty_body_and_falls_back_to_earlier_entry(seeded_session):
    """日記は任意入力のため空文字の記録がありうる。「前回」として提示する意味が無いため
    スキップし、その前に本文のある記録まで遡る。"""
    goal = _make_goal(seeded_session)
    record_service_exam.finalize_record(
        seeded_session, dt.date(2026, 3, 8), [], [_diary(goal.id, "3/8の所感")], dt.date(2026, 3, 8)
    )
    record_service_exam.finalize_record(
        seeded_session, dt.date(2026, 3, 9), [], [_diary(goal.id, "")], dt.date(2026, 3, 9)
    )

    entry = record_service_exam.get_previous_diary_entry(
        seeded_session, goal.id, dt.date(2026, 3, 10)
    )

    assert entry.record_date == dt.date(2026, 3, 8)


def test_get_previous_diary_entry_uses_learned_text_for_new_entries(seeded_session):
    """新規入力は学んだこと（diary_learned）だけで保存されるため、それを前回ヒントとして返す。"""
    goal = _make_goal(seeded_session)
    record_service_exam.finalize_record(
        seeded_session,
        dt.date(2026, 3, 9),
        [],
        [_diary(goal.id, diary_learned="3/9に学んだこと")],
        dt.date(2026, 3, 9),
    )

    entry = record_service_exam.get_previous_diary_entry(
        seeded_session, goal.id, dt.date(2026, 3, 10)
    )

    assert entry.record_date == dt.date(2026, 3, 9)
    assert entry.body == "3/9に学んだこと"


def test_get_previous_diary_entry_prefers_learned_text_over_legacy_body(seeded_session):
    goal = _make_goal(seeded_session)
    record_service_exam.finalize_record(
        seeded_session,
        dt.date(2026, 3, 9),
        [],
        [_diary(goal.id, diary_body="旧い本文", diary_learned="学んだこと")],
        dt.date(2026, 3, 9),
    )

    entry = record_service_exam.get_previous_diary_entry(
        seeded_session, goal.id, dt.date(2026, 3, 10)
    )

    assert entry.body == "学んだこと"


def test_get_previous_diary_entry_falls_back_to_legacy_body_when_learned_is_empty(seeded_session):
    goal = _make_goal(seeded_session)
    record_service_exam.finalize_record(
        seeded_session,
        dt.date(2026, 3, 9),
        [],
        [_diary(goal.id, diary_body="旧い本文", diary_learned="")],
        dt.date(2026, 3, 9),
    )

    entry = record_service_exam.get_previous_diary_entry(
        seeded_session, goal.id, dt.date(2026, 3, 10)
    )

    assert entry.body == "旧い本文"


def test_get_previous_diary_entry_returns_none_when_no_record_exists(seeded_session):
    goal = _make_goal(seeded_session)

    entry = record_service_exam.get_previous_diary_entry(
        seeded_session, goal.id, dt.date(2026, 3, 10)
    )

    assert entry is None


# --- 時間枠別入力の検証（資格試験分） ---


def test_register_progress_rejects_negative_slot_minutes(seeded_session):
    """時間枠ごとの投下時間は0以上（仕様書10章「数値範囲」）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    slot = _make_slot(seeded_session)
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service_common.register_progress(
            seeded_session, today, [_log(material.id, slot_minutes={slot.id: -1})], today
        )


def test_register_progress_skips_zero_slot_minutes(seeded_session):
    """0分の入力は内訳の行を作らない（データ構造編5.4）。合計も未入力（None）となる。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    slot = _make_slot(seeded_session)
    today = dt.date(2026, 3, 10)

    record = record_service_common.register_progress(
        seeded_session, today, [_log(material.id, slot_minutes={slot.id: 0})], today
    )

    assert record.study_logs[0].slot_times == []
    assert record.study_logs[0].minutes_spent is None


def test_register_progress_rejects_unknown_slot(seeded_session):
    """存在しない時間枠への投下時間は拒否する。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    today = dt.date(2026, 3, 10)

    with pytest.raises(ValidationError):
        record_service_common.register_progress(
            seeded_session, today, [_log(material.id, slot_minutes={9999: 30})], today
        )


# --- 週次要約の無効化（G4、開発Todo S06） ---


def _make_weekly_summary(session, goal, week_start, week_end=None, **overrides):
    defaults = dict(
        goal_id=goal.id,
        week_start_date=week_start,
        week_end_date=week_end or week_start + dt.timedelta(days=6),
        summary_body="既に生成済み",
    )
    defaults.update(overrides)
    summary = WeeklySummary(**defaults)
    session.add(summary)
    session.flush()
    return summary


def test_register_progress_invalidates_existing_weekly_summary_for_edited_week(seeded_session):
    """既に週次要約が生成済みの過去週へ進捗のみ登録で実績を追記すると、その週の要約
    （非匿名化・匿名化とも）が削除される（G4。register_progressはfinalize系と異なり
    バックデート制限を持たないため、完了済みの週も無制限に編集できてしまう）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    week_start = dt.date(2026, 3, 2)  # 月曜
    edited_date = dt.date(2026, 3, 4)  # 同じ週の水曜
    non_anon = _make_weekly_summary(seeded_session, goal, week_start)
    anon = _make_weekly_summary(seeded_session, goal, week_start, is_anonymized=True)

    record_service_common.register_progress(
        seeded_session, edited_date, [_log(material.id)], dt.date(2026, 3, 10)
    )

    assert seeded_session.get(WeeklySummary, non_anon.id) is None
    assert seeded_session.get(WeeklySummary, anon.id) is None


def test_register_progress_does_not_invalidate_other_weeks(seeded_session):
    """編集した週以外の既存の週次要約は残る。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    other_week = _make_weekly_summary(seeded_session, goal, dt.date(2026, 2, 23))

    record_service_common.register_progress(
        seeded_session, dt.date(2026, 3, 4), [_log(material.id)], dt.date(2026, 3, 10)
    )

    assert seeded_session.get(WeeklySummary, other_week.id) is not None


def test_finalize_record_invalidates_existing_weekly_summary_via_diary(seeded_session):
    """日記の確定（finalize_record）でも、同じ週の既存の週次要約が削除される。"""
    goal = _make_goal(seeded_session)
    week_start = dt.date(2026, 3, 2)
    target_date = dt.date(2026, 3, 3)  # 前日（_ensure_finalizable_dateの許容範囲内）
    today = dt.date(2026, 3, 4)
    summary = _make_weekly_summary(seeded_session, goal, week_start)

    record_service_exam.finalize_record(
        seeded_session, target_date, [], [_diary(goal.id, diary_learned="学んだこと")], today
    )

    assert seeded_session.get(WeeklySummary, summary.id) is None
