"""milestone_service_exam のテスト（開発Todo_節目のお祝い_v1.0 §3.3 B-07、
開発Todo_単語帳_v1.0 要件E）。"""

import datetime as dt

from app.constants.app_setting_keys import (
    MILESTONE_EXAM_OVERALL_PROGRESS_THRESHOLDS,
    MILESTONE_VOCAB_MASTERED_TERMS_THRESHOLDS,
    VOCAB_MASTERY_STREAK,
)
from app.constants.enums import GoalCategory, GoalStatus, MilestoneType
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, StudyLog
from app.models.setting import AppSetting
from app.services import milestone_service_exam as svc
from tests.vocab_helpers import make_answer_log, make_card, make_deck


def _make_goal(db_session, start_date=dt.date(2026, 1, 1)):
    goal = Goal(
        name="資格節目検証",
        category=GoalCategory.EXAM,
        start_date=start_date,
        status=GoalStatus.ACTIVE,
    )
    db_session.add(goal)
    db_session.flush()
    return goal


def _make_material(db_session, goal_id, total_amount=100.0, planned_cycles=1, is_active=True):
    material = Material(
        goal_id=goal_id,
        name="教材A",
        unit_label="問",
        total_amount=total_amount,
        planned_cycles=planned_cycles,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 12, 31),
        display_order=1,
        is_active=is_active,
    )
    db_session.add(material)
    db_session.flush()
    return material


def _add_study_log(db_session, material_id, record_date, amount, cycle_number=1):
    record = db_session.query(DailyRecord).filter(DailyRecord.record_date == record_date).first()
    if record is None:
        record = DailyRecord(record_date=record_date)
        db_session.add(record)
        db_session.flush()
    db_session.add(
        StudyLog(
            daily_record_id=record.id,
            material_id=material_id,
            amount_completed=amount,
            cycle_number=cycle_number,
        )
    )
    db_session.flush()


def _set_threshold(session, key, value):
    row = session.get(AppSetting, key)
    row.value = value


def test_detect_exam_milestones_returns_empty_without_active_materials(seeded_session):
    goal = _make_goal(seeded_session)

    assert svc.detect_exam_milestones(seeded_session, goal, dt.date(2026, 1, 10)) == []


def test_detect_exam_milestones_ignores_inactive_materials(seeded_session):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal.id, total_amount=10.0, is_active=False)

    assert svc.detect_exam_milestones(seeded_session, goal, dt.date(2026, 1, 10)) == []


def test_detect_exam_milestones_reports_material_cycle_completion(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal.id, total_amount=10.0, planned_cycles=2)
    _add_study_log(seeded_session, material.id, dt.date(2026, 1, 1), 10.0, cycle_number=1)

    pending = svc.detect_exam_milestones(seeded_session, goal, dt.date(2026, 1, 1))

    keys = {(p.milestone_type, p.milestone_key) for p in pending}
    assert (MilestoneType.EXAM_MATERIAL_CYCLE_COMPLETED, f"{material.id}:1") in keys


def test_detect_exam_milestones_reports_multiple_completed_cycles(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal.id, total_amount=10.0, planned_cycles=3)
    _add_study_log(seeded_session, material.id, dt.date(2026, 1, 1), 25.0, cycle_number=1)

    pending = svc.detect_exam_milestones(seeded_session, goal, dt.date(2026, 1, 1))

    keys = {
        p.milestone_key
        for p in pending
        if p.milestone_type == MilestoneType.EXAM_MATERIAL_CYCLE_COMPLETED
    }
    assert keys == {f"{material.id}:1", f"{material.id}:2"}


def test_detect_exam_milestones_reports_overall_progress_threshold(seeded_session):
    _set_threshold(seeded_session, MILESTONE_EXAM_OVERALL_PROGRESS_THRESHOLDS, "25,50,75")
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal.id, total_amount=100.0, planned_cycles=1)
    _add_study_log(seeded_session, material.id, dt.date(2026, 1, 1), 60.0)

    pending = svc.detect_exam_milestones(seeded_session, goal, dt.date(2026, 1, 1))

    keys = {
        p.milestone_key for p in pending if p.milestone_type == MilestoneType.EXAM_OVERALL_PROGRESS
    }
    assert keys == {"25", "50"}


def test_detect_exam_milestones_reports_vocab_mastered_terms_threshold(seeded_session):
    """開発Todo_単語帳_v1.0 要件E E-U2：単語帳の習得用語数（全単語帳の合計）の節目。"""
    _set_threshold(seeded_session, MILESTONE_VOCAB_MASTERED_TERMS_THRESHOLDS, "1,3")
    _set_threshold(seeded_session, VOCAB_MASTERY_STREAK, "1")
    goal = _make_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)
    make_answer_log(seeded_session, card, is_correct=True, answered_at=dt.datetime(2026, 1, 1))

    pending = svc.detect_exam_milestones(seeded_session, goal, dt.date(2026, 1, 1))

    keys = {
        p.milestone_key for p in pending if p.milestone_type == MilestoneType.VOCAB_MASTERED_TERMS
    }
    assert keys == {"1"}


def test_detect_exam_milestones_detects_vocab_mastery_even_without_any_material(seeded_session):
    """教材が0件（単語帳のみの下書き中の目標）でも、単語帳の習得判定は行われること。"""
    _set_threshold(seeded_session, MILESTONE_VOCAB_MASTERED_TERMS_THRESHOLDS, "1")
    _set_threshold(seeded_session, VOCAB_MASTERY_STREAK, "1")
    goal = _make_goal(seeded_session)
    deck = make_deck(seeded_session, goal)
    card = make_card(seeded_session, deck)
    make_answer_log(seeded_session, card, is_correct=True, answered_at=dt.datetime(2026, 1, 1))

    pending = svc.detect_exam_milestones(seeded_session, goal, dt.date(2026, 1, 1))

    assert {(p.milestone_type, p.milestone_key) for p in pending} == {
        (MilestoneType.VOCAB_MASTERED_TERMS, "1")
    }


def test_detect_exam_milestones_vocab_mastery_is_empty_without_any_deck(seeded_session):
    goal = _make_goal(seeded_session)

    assert svc.detect_exam_milestones(seeded_session, goal, dt.date(2026, 1, 1)) == []
