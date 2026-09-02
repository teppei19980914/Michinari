"""目標のCRUD・状態遷移・計画基準値の再設定契機（設計書データ構造編5.3・6.2、
仕様書6.2・7.1・10章、ロジック・プロンプト編12.1、実装フェーズ分割計画書Phase3）。

resolve_today / resolve_treat_holiday_as_buffer / record_baseline_for_material /
ensure_goal_editable は subject_service・material_service からも共通処理として呼ばれる
（CLAUDE.md DRYの原則）。
"""

import datetime as dt

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.constants.app_setting_keys import CALENDAR_DAY_BOUNDARY_HOUR, HOLIDAY_TREAT_AS_BUFFER
from app.constants.enums import BaselineReason, DayType, GoalCategory, GoalStatus
from app.models.base import utcnow
from app.models.goal import Goal, LoadProfile
from app.models.material import Material, PlanBaseline
from app.services import (
    baseline_service,
    calendar_service,
    cycle_service,
    quota_service,
    setting_reader,
)
from app.services.exceptions import (
    InvalidStateTransitionError,
    NotFoundError,
    ResourceRatioExceededError,
    ValidationError,
)

#: resource_ratio合計の浮動小数点誤差許容値（100.0%ちょうどの保存を誤って拒否しないため）。
_RATIO_TOLERANCE = 1e-9

#: クローズ済みとみなす目標状態（仕様書6.2「クローズの場合、全項目を読み取り専用とする」）。
_CLOSED_STATUSES = (GoalStatus.CLOSED_WITH_RESULT, GoalStatus.CLOSED_WITHOUT_RESULT)


def resolve_today(session: Session) -> dt.date:
    """1日の境界時刻を考慮した論理的な本日を返す（ロジック・プロンプト編3.1）。"""
    boundary_hour = setting_reader.get_int(session, CALENDAR_DAY_BOUNDARY_HOUR)
    return calendar_service.resolve_logical_today(dt.datetime.now(), boundary_hour)


def resolve_treat_holiday_as_buffer(session: Session) -> bool:
    return setting_reader.get_bool(session, HOLIDAY_TREAT_AS_BUFFER)


def record_baseline_for_material(
    session: Session,
    material: Material,
    reason: BaselineReason,
    today: dt.date,
    treat_holiday_as_buffer: bool,
) -> PlanBaseline:
    """計画基準値を再計算して記録する（ロジック・プロンプト編12.1〜12.2）。

    quota・remaining・残計画日数は本関数がPhase2サービスを組み合わせて算出する
    （baseline_serviceは記録・取得のみを担うため、算出はAPI層=Phase3の責務）。
    """
    quota = quota_service.compute_material_quota(
        session, material.goal, material, today, treat_holiday_as_buffer
    )
    progress = cycle_service.get_material_progress(session, material)
    day_types = calendar_service.resolve_day_types(
        session, today, material.due_date, treat_holiday_as_buffer
    )
    plan_days = sum(1 for day_type in day_types.values() if day_type == DayType.PLAN)
    return baseline_service.record_baseline(
        session,
        material,
        reason,
        today,
        baseline_daily_quota=quota,
        remaining_at_baseline=progress.remaining,
        plan_days_at_baseline=plan_days,
    )


def ensure_goal_editable(goal: Goal) -> None:
    """クローズ済み目標への更新を拒否する（仕様書6.2「クローズの場合、全項目を読み取り専用」）。"""
    if goal.status in _CLOSED_STATUSES:
        raise InvalidStateTransitionError(f"クローズ済みの目標(id={goal.id})は更新できません")


def _validate_resource_ratio(
    session: Session, candidate_ratio: float, exclude_goal_id: int
) -> None:
    """ACTIVEな目標のresource_ratio合計が1.0を超えないか検証する（データ構造編5.3）。"""
    other_total = (
        session.query(func.sum(Goal.resource_ratio))
        .filter(Goal.status == GoalStatus.ACTIVE, Goal.id != exclude_goal_id)
        .scalar()
        or 0.0
    )
    total = other_total + candidate_ratio
    if total > 1.0 + _RATIO_TOLERANCE:
        raise ResourceRatioExceededError(total)


def get_goal(session: Session, goal_id: int) -> Goal:
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise NotFoundError("目標", goal_id)
    return goal


def list_goals(session: Session) -> list[Goal]:
    return session.query(Goal).order_by(Goal.id).all()


def create_goal(
    session: Session,
    *,
    name: str,
    start_date: dt.date,
    memo: str | None,
    category: GoalCategory = GoalCategory.EXAM,
) -> Goal:
    goal = Goal(
        category=category,
        name=name,
        start_date=start_date,
        status=GoalStatus.DRAFT,
        resource_ratio=0.0,
        memo=memo,
    )
    session.add(goal)
    session.flush()
    return goal


def update_goal(
    session: Session,
    goal: Goal,
    *,
    name: str | None = None,
    start_date: dt.date | None = None,
    memo: str | None = None,
    resource_ratio: float | None = None,
) -> Goal:
    ensure_goal_editable(goal)

    if name is not None:
        goal.name = name
    if start_date is not None:
        goal.start_date = start_date
    if memo is not None:
        goal.memo = memo
    if resource_ratio is not None:
        # 読書目標はリソース配分プールの対象外（要件定義書R-64）。resource_ratioは常に0のまま。
        if goal.category == GoalCategory.READING:
            raise ValidationError("読書目標にはリソース配分を設定できません")
        if not (0.0 <= resource_ratio <= 1.0):
            raise ValidationError("リソース配分比率は0.0〜1.0で入力してください")
        if goal.status == GoalStatus.ACTIVE:
            _validate_resource_ratio(session, resource_ratio, exclude_goal_id=goal.id)
        goal.resource_ratio = resource_ratio

    session.flush()
    return goal


def delete_goal(session: Session, goal: Goal) -> None:
    if goal.status != GoalStatus.DRAFT:
        raise InvalidStateTransitionError("下書き状態の目標のみ削除できます")
    session.delete(goal)
    session.flush()


def activate_goal(session: Session, goal: Goal) -> Goal:
    """下書き→進行中（仕様書7.1）。前提未達・リソース超過時は例外を送出する。

    読書目標（category=READING）は書籍の登録のみを前提とし、教材・リソース配分・
    計画基準値（EXAM固有の計画管理、要件定義書R-63）は対象外とする。
    """
    if goal.status != GoalStatus.DRAFT:
        raise InvalidStateTransitionError("下書き状態の目標のみ開始できます")

    if goal.category == GoalCategory.READING:
        if goal.book is None:
            raise ValidationError("書籍を登録してください")
    else:
        if not goal.exam_subjects:
            raise ValidationError("試験科目を1件以上登録してください")
        if not goal.materials:
            raise ValidationError("教材を1件以上登録してください")
        _validate_resource_ratio(session, goal.resource_ratio, exclude_goal_id=goal.id)

    goal.status = GoalStatus.ACTIVE
    goal.activated_at = utcnow()
    session.flush()

    if goal.category == GoalCategory.EXAM:
        today = resolve_today(session)
        treat_holiday_as_buffer = resolve_treat_holiday_as_buffer(session)
        for material in goal.materials:
            if material.is_active:
                record_baseline_for_material(
                    session, material, BaselineReason.INITIAL, today, treat_holiday_as_buffer
                )
    return goal


def pause_goal(session: Session, goal: Goal) -> Goal:
    """進行中→一時停止（仕様書7.1）。リソース配分は解放される（合計計算から除外）。"""
    if goal.status != GoalStatus.ACTIVE:
        raise InvalidStateTransitionError("進行中の目標のみ一時停止できます")
    goal.status = GoalStatus.PAUSED
    session.flush()
    return goal


def resume_goal(session: Session, goal: Goal) -> Goal:
    """一時停止→進行中（仕様書7.1）。リソースの空きが不足する場合はエラーとする。"""
    if goal.status != GoalStatus.PAUSED:
        raise InvalidStateTransitionError("一時停止中の目標のみ復帰できます")
    _validate_resource_ratio(session, goal.resource_ratio, exclude_goal_id=goal.id)
    goal.status = GoalStatus.ACTIVE
    session.flush()
    return goal


def close_goal(session: Session, goal: Goal, *, confirm_without_result: bool = False) -> Goal:
    """進行中→クローズ（仕様書7.1）。

    全科目の受験結果が登録済みなら自動的に「結果あり」でクローズする。
    未登録の科目が残る場合は confirm_without_result=True の明示確認を必須とする。
    総括レポートの生成(AI連携)はPhase10の責務であり、本関数の成否には影響させない。

    読書目標（category=READING）は exam_subjects が常に空のため has_all_results は
    常にFalseとなり、本関数は confirm_without_result=True を要求したうえで
    CLOSED_WITHOUT_RESULT（中断）へ遷移させる（仕様書7.1）。読了（CLOSED_WITH_RESULT）は
    本関数ではなく book_service.complete_book（POST /books/{id}/complete）を用いる。
    """
    if goal.status != GoalStatus.ACTIVE:
        raise InvalidStateTransitionError("進行中の目標のみクローズできます")

    has_all_results = bool(goal.exam_subjects) and all(
        subject.exam_result is not None for subject in goal.exam_subjects
    )
    if has_all_results:
        goal.status = GoalStatus.CLOSED_WITH_RESULT
    else:
        if not confirm_without_result:
            raise InvalidStateTransitionError(
                "受験結果が未登録の科目があります。結果なしでクローズする場合は確認が必要です"
            )
        goal.status = GoalStatus.CLOSED_WITHOUT_RESULT

    goal.closed_at = utcnow()
    session.flush()
    return goal


def get_baselines(session: Session, goal: Goal) -> list[PlanBaseline]:
    """目標配下の全教材のリプラン履歴を取得する（データ構造編5.3、Phase3実装対象「リプラン履歴の取得」）。"""
    return (
        session.query(PlanBaseline)
        .join(Material, PlanBaseline.material_id == Material.id)
        .filter(Material.goal_id == goal.id)
        .order_by(PlanBaseline.effective_from.desc(), PlanBaseline.id.desc())
        .all()
    )


def get_load_profile(session: Session, load_profile_id: int) -> LoadProfile:
    profile = session.get(LoadProfile, load_profile_id)
    if profile is None:
        raise NotFoundError("負荷プロファイル", load_profile_id)
    return profile


def list_load_profiles(session: Session, goal: Goal) -> list[LoadProfile]:
    return (
        session.query(LoadProfile)
        .filter(LoadProfile.goal_id == goal.id)
        .order_by(LoadProfile.date_from)
        .all()
    )


def _validate_load_profile_period(
    session: Session,
    goal: Goal,
    date_from: dt.date,
    date_to: dt.date,
    coefficient: float,
    exclude_id: int | None,
) -> None:
    if date_from > date_to:
        raise ValidationError("適用開始日は適用終了日以前にしてください")
    if coefficient <= 0:
        raise ValidationError("負荷係数は正の数で入力してください")

    query = session.query(LoadProfile).filter(
        LoadProfile.goal_id == goal.id,
        LoadProfile.date_from <= date_to,
        LoadProfile.date_to >= date_from,
    )
    if exclude_id is not None:
        query = query.filter(LoadProfile.id != exclude_id)
    if query.first() is not None:
        raise ValidationError("既存の負荷プロファイルと期間が重複しています")


def create_load_profile(
    session: Session,
    goal: Goal,
    *,
    date_from: dt.date,
    date_to: dt.date,
    coefficient: float,
    note: str | None,
) -> LoadProfile:
    ensure_goal_editable(goal)
    _validate_load_profile_period(session, goal, date_from, date_to, coefficient, exclude_id=None)
    profile = LoadProfile(
        goal_id=goal.id, date_from=date_from, date_to=date_to, coefficient=coefficient, note=note
    )
    session.add(profile)
    session.flush()
    return profile


def update_load_profile(
    session: Session,
    profile: LoadProfile,
    *,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    coefficient: float | None = None,
    note: str | None = None,
) -> LoadProfile:
    ensure_goal_editable(profile.goal)
    new_from = date_from if date_from is not None else profile.date_from
    new_to = date_to if date_to is not None else profile.date_to
    new_coefficient = coefficient if coefficient is not None else profile.coefficient
    _validate_load_profile_period(
        session, profile.goal, new_from, new_to, new_coefficient, exclude_id=profile.id
    )
    profile.date_from = new_from
    profile.date_to = new_to
    profile.coefficient = new_coefficient
    if note is not None:
        profile.note = note
    session.flush()
    return profile


def delete_load_profile(session: Session, profile: LoadProfile) -> None:
    ensure_goal_editable(profile.goal)
    session.delete(profile)
    session.flush()
