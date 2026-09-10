"""サービス層の防御的バリデーションの直接テスト。

これらの分岐は Pydantic スキーマ（例: Field(ge=0)）によりAPI層では既に到達不能だが、
CLAUDE.md「サービス層でのHTTP例外の送出禁止」の方針上、サービス関数は呼び出し元が
API層とは限らない前提で独立して自己防御する。境界値の実装自体を直接検証する。
"""

import datetime as dt

import pytest

from app.constants.app_setting_keys import CALENDAR_DAY_BOUNDARY_HOUR, HOLIDAY_TREAT_AS_BUFFER
from app.constants.enums import (
    Environment,
    ExamDateType,
    ExamResultType,
    GoalStatus,
    PassingScoreType,
    QualityMetricType,
)
from app.models.goal import Goal
from app.models.record import ExamResult
from app.models.setting import AppSetting
from app.services import goal_service, material_service, resource_service, subject_service
from app.services.exceptions import AppSettingNotFoundError, ValidationError


def _seed_goal(session, resource_ratio: float = 0.5) -> Goal:
    goal = goal_service.create_goal(
        session, name="目標A", start_date=dt.date(2026, 1, 1), memo=None
    )
    goal.resource_ratio = resource_ratio
    session.flush()
    return goal


def test_update_goal_rejects_resource_ratio_out_of_range(seeded_session):
    goal = _seed_goal(seeded_session)
    with pytest.raises(ValidationError):
        goal_service.update_goal(
            seeded_session,
            goal,
        )


def test_create_load_profile_rejects_non_positive_coefficient(seeded_session):
    goal = _seed_goal(seeded_session)
    with pytest.raises(ValidationError):
        goal_service.create_load_profile(
            seeded_session,
            goal,
            date_from=dt.date(2026, 3, 1),
            date_to=dt.date(2026, 3, 31),
            coefficient=0,
            note=None,
        )


def test_close_goal_with_all_results_registered_closes_with_result(seeded_session):
    goal = _seed_goal(seeded_session)
    subject = subject_service.create_subject(
        seeded_session,
        goal,
        name="科目A",
        exam_date_type=ExamDateType.FIXED,
        exam_date_from=None,
        exam_date_to=None,
        exam_date_fixed=dt.date(2026, 6, 1),
        passing_score=None,
    )
    material_service.create_material(
        seeded_session,
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
    goal_service.activate_goal(seeded_session, goal)
    seeded_session.add(
        ExamResult(
            subject_id=subject.id, taken_date=dt.date(2026, 6, 1), result=ExamResultType.PASS
        )
    )
    seeded_session.flush()

    goal_service.close_goal(seeded_session, goal)
    assert goal.status == GoalStatus.CLOSED_WITH_RESULT


def test_create_material_rejects_empty_subject_ids(seeded_session):
    goal = _seed_goal(seeded_session)
    with pytest.raises(ValidationError):
        material_service.create_material(
            seeded_session,
            goal,
            name="教材A",
            unit_label="ページ",
            total_amount=100,
            planned_cycles=1,
            subject_ids=[],
            start_date=dt.date(2026, 1, 1),
            due_date=None,
            due_date_is_manual=False,
            required_block_minutes=None,
            required_environment=Environment.ANY,
            quality_metric_type=QualityMetricType.NONE,
        )


def test_create_material_rejects_negative_total_amount(seeded_session):
    goal = _seed_goal(seeded_session)
    subject = subject_service.create_subject(
        seeded_session,
        goal,
        name="科目A",
        exam_date_type=ExamDateType.FIXED,
        exam_date_from=None,
        exam_date_to=None,
        exam_date_fixed=dt.date(2026, 6, 1),
        passing_score=None,
    )
    with pytest.raises(ValidationError):
        material_service.create_material(
            seeded_session,
            goal,
            name="教材A",
            unit_label="ページ",
            total_amount=-1,
            planned_cycles=1,
            subject_ids=[subject.id],
            start_date=dt.date(2026, 1, 1),
            due_date=None,
            due_date_is_manual=False,
            required_block_minutes=None,
            required_environment=Environment.ANY,
            quality_metric_type=QualityMetricType.NONE,
        )


def test_create_material_rejects_planned_cycles_below_one(seeded_session):
    goal = _seed_goal(seeded_session)
    subject = subject_service.create_subject(
        seeded_session,
        goal,
        name="科目A",
        exam_date_type=ExamDateType.FIXED,
        exam_date_from=None,
        exam_date_to=None,
        exam_date_fixed=dt.date(2026, 6, 1),
        passing_score=None,
    )
    with pytest.raises(ValidationError):
        material_service.create_material(
            seeded_session,
            goal,
            name="教材A",
            unit_label="ページ",
            total_amount=100,
            planned_cycles=0,
            subject_ids=[subject.id],
            start_date=dt.date(2026, 1, 1),
            due_date=None,
            due_date_is_manual=False,
            required_block_minutes=None,
            required_environment=Environment.ANY,
            quality_metric_type=QualityMetricType.NONE,
        )


def _create_material_for_update_tests(session, goal: Goal):
    subject = subject_service.create_subject(
        session,
        goal,
        name="科目A",
        exam_date_type=ExamDateType.FIXED,
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
        planned_cycles=2,
        subject_ids=[subject.id],
        start_date=dt.date(2026, 1, 1),
        due_date=None,
        due_date_is_manual=False,
        required_block_minutes=None,
        required_environment=Environment.ANY,
        quality_metric_type=QualityMetricType.NONE,
    )


def test_update_material_rejects_planned_cycles_below_one(seeded_session):
    goal = _seed_goal(seeded_session)
    material = _create_material_for_update_tests(seeded_session, goal)
    with pytest.raises(ValidationError):
        material_service.update_material(seeded_session, material, planned_cycles=0)


def test_update_material_rejects_negative_total_amount(seeded_session):
    goal = _seed_goal(seeded_session)
    material = _create_material_for_update_tests(seeded_session, goal)
    with pytest.raises(ValidationError):
        material_service.update_material(seeded_session, material, total_amount=-5)


def test_create_slot_rejects_empty_weekdays(seeded_session):
    with pytest.raises(ValidationError):
        resource_service.create_slot(
            seeded_session,
            name="通勤",
            start_time=dt.time(7, 0),
            end_time=dt.time(8, 0),
            environment=Environment.MOBILE,
            weekdays=[],
        )


def test_create_subject_rejects_passing_score_out_of_range(seeded_session):
    goal = _seed_goal(seeded_session)
    with pytest.raises(ValidationError):
        subject_service.create_subject(
            seeded_session,
            goal,
            name="科目A",
            exam_date_type=ExamDateType.FIXED,
            exam_date_from=None,
            exam_date_to=None,
            exam_date_fixed=dt.date(2026, 6, 1),
            passing_score=150,
        )


def test_create_subject_accepts_raw_score_within_max(seeded_session):
    goal = _seed_goal(seeded_session)
    subject = subject_service.create_subject(
        seeded_session,
        goal,
        name="科目A",
        exam_date_type=ExamDateType.FIXED,
        exam_date_from=None,
        exam_date_to=None,
        exam_date_fixed=dt.date(2026, 6, 1),
        passing_score=700,
        passing_score_type=PassingScoreType.RAW_SCORE,
        passing_score_max=1000,
    )
    assert subject.passing_score == 700
    assert subject.passing_score_max == 1000


def test_create_subject_rejects_raw_score_without_max(seeded_session):
    goal = _seed_goal(seeded_session)
    with pytest.raises(ValidationError):
        subject_service.create_subject(
            seeded_session,
            goal,
            name="科目A",
            exam_date_type=ExamDateType.FIXED,
            exam_date_from=None,
            exam_date_to=None,
            exam_date_fixed=dt.date(2026, 6, 1),
            passing_score=700,
            passing_score_type=PassingScoreType.RAW_SCORE,
            passing_score_max=None,
        )


def test_create_subject_rejects_raw_score_exceeding_max(seeded_session):
    goal = _seed_goal(seeded_session)
    with pytest.raises(ValidationError):
        subject_service.create_subject(
            seeded_session,
            goal,
            name="科目A",
            exam_date_type=ExamDateType.FIXED,
            exam_date_from=None,
            exam_date_to=None,
            exam_date_fixed=dt.date(2026, 6, 1),
            passing_score=1100,
            passing_score_type=PassingScoreType.RAW_SCORE,
            passing_score_max=1000,
        )


def test_create_subject_rejects_percentage_with_max(seeded_session):
    goal = _seed_goal(seeded_session)
    with pytest.raises(ValidationError):
        subject_service.create_subject(
            seeded_session,
            goal,
            name="科目A",
            exam_date_type=ExamDateType.FIXED,
            exam_date_from=None,
            exam_date_to=None,
            exam_date_fixed=dt.date(2026, 6, 1),
            passing_score=60,
            passing_score_type=PassingScoreType.PERCENTAGE,
            passing_score_max=100,
        )


def test_create_subject_rejects_max_without_passing_score(seeded_session):
    goal = _seed_goal(seeded_session)
    with pytest.raises(ValidationError):
        subject_service.create_subject(
            seeded_session,
            goal,
            name="科目A",
            exam_date_type=ExamDateType.FIXED,
            exam_date_from=None,
            exam_date_to=None,
            exam_date_fixed=dt.date(2026, 6, 1),
            passing_score=None,
            passing_score_max=1000,
        )


def test_create_subject_rejects_non_positive_max(seeded_session):
    goal = _seed_goal(seeded_session)
    with pytest.raises(ValidationError):
        subject_service.create_subject(
            seeded_session,
            goal,
            name="科目A",
            exam_date_type=ExamDateType.FIXED,
            exam_date_from=None,
            exam_date_to=None,
            exam_date_fixed=dt.date(2026, 6, 1),
            passing_score=50,
            passing_score_type=PassingScoreType.RAW_SCORE,
            passing_score_max=0,
        )


def test_update_subject_switching_to_percentage_clears_max(seeded_session):
    goal = _seed_goal(seeded_session)
    subject = subject_service.create_subject(
        seeded_session,
        goal,
        name="科目A",
        exam_date_type=ExamDateType.FIXED,
        exam_date_from=None,
        exam_date_to=None,
        exam_date_fixed=dt.date(2026, 6, 1),
        passing_score=700,
        passing_score_type=PassingScoreType.RAW_SCORE,
        passing_score_max=1000,
    )
    subject_service.update_subject(
        seeded_session,
        subject,
        passing_score=60,
        passing_score_type=PassingScoreType.PERCENTAGE,
    )
    assert subject.passing_score_type == PassingScoreType.PERCENTAGE
    assert subject.passing_score_max is None
    assert subject.passing_score == 60


def test_update_day_boundary_hour_rejects_out_of_range(seeded_session):
    with pytest.raises(ValidationError):
        resource_service.update_day_boundary_hour(seeded_session, 12)


def test_update_day_boundary_hour_missing_setting_raises_app_setting_not_found(seeded_session):
    seeded_session.query(AppSetting).filter(AppSetting.key == CALENDAR_DAY_BOUNDARY_HOUR).delete()
    seeded_session.flush()
    with pytest.raises(AppSettingNotFoundError):
        resource_service.update_day_boundary_hour(seeded_session, 4)


def test_update_holiday_treat_as_buffer_missing_setting_raises_app_setting_not_found(
    seeded_session,
):
    seeded_session.query(AppSetting).filter(AppSetting.key == HOLIDAY_TREAT_AS_BUFFER).delete()
    seeded_session.flush()
    with pytest.raises(AppSettingNotFoundError):
        resource_service.update_holiday_treat_as_buffer(seeded_session, False)
