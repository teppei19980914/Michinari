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
from app.models.record import (
    ChatMessage,
    DailyGoalDiary,
    DailyRecord,
    ReadingLog,
    RecordComment,
    StudyLog,
)
from app.services import (
    baseline_service,
    calendar_service,
    cycle_service,
    quota_service,
    setting_reader,
)
from app.services.exceptions import (
    BookHasReadingLogsError,
    ExamSubjectRequiredError,
    InvalidStateTransitionError,
    MaterialHasStudyLogsError,
    MaterialRequiredError,
    NotFoundError,
    ResourceRatioExceededError,
    ResourceRatioRequiredError,
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

    quota・残計画日数の算出には today ではなく max(today, material.start_date)（quota_base_date、
    P(m)の起点）を用いる。基準値の再設定はユーザー操作（目標開始・教材変更・リプラン等）が
    契機であり、開始日到来をトリガーとした自動再設定は存在しない。学習期間開始前に today の
    まま算出すると quota(m, T)=0（quota_service.compute_material_quota、7.1式のS(m)≤T条件）
    が baseline_daily_quotaとして固定され、check_warning（threshold_service.py）の
    「baseline<=0なら判定しない」ガードにより、教材が開始日を迎えた後もペースが乱れた際の
    警告が永久に発火しなくなる（デグレ）。開始日時点で見込まれるペースを基準値として
    記録することでこれを避ける。quotaとplan_days_at_baselineが異なる日付窓（P(m)の起点）
    から算出されると baseline_daily_quota × plan_days_at_baseline ≠ remaining_at_baseline
    という不整合が生じるため、両者は同じ quota_base_date を起点に統一する（記録レコード自体の
    effective_from は、baseline_service.get_current_baseline が「現在時点で有効な基準値」を
    検索するための実際の記録日=todayのままとし、quota_base_dateとは区別する）。
    """
    quota_base_date = max(today, material.start_date)
    quota = quota_service.compute_material_quota(
        session, material.goal, material, quota_base_date, treat_holiday_as_buffer
    )
    progress = cycle_service.get_material_progress(session, material)
    day_types = calendar_service.resolve_day_types(
        session, quota_base_date, material.due_date, treat_holiday_as_buffer
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


def archive_goal(session: Session, goal: Goal) -> Goal:
    """クローズ済み目標をアーカイブする（論理削除、仕様書7.1.1）。"""
    if goal.status not in _CLOSED_STATUSES:
        raise InvalidStateTransitionError("クローズ済みの目標のみアーカイブできます")
    if goal.archived_at is not None:
        raise InvalidStateTransitionError("既にアーカイブ済みです")
    goal.archived_at = utcnow()
    session.flush()
    return goal


def unarchive_goal(session: Session, goal: Goal) -> Goal:
    """アーカイブを解除し、通常の一覧表示へ戻す（仕様書7.1.1）。statusは変更しない。"""
    if goal.archived_at is None:
        raise InvalidStateTransitionError("アーカイブされていません")
    goal.archived_at = None
    session.flush()
    return goal


def _cascade_delete_activity_logs(session: Session, goal: Goal) -> None:
    """完全削除でstudy_log／reading_logも道連れにする場合の先行削除（データ構造編4.2）。

    material→study_log・book→reading_logはいずれもDB上RESTRICT（PRAGMA foreign_keys=ON、
    database.py）のため、Goal本体をsession.delete()する前に本関数で明示的に削除し
    flushしておく必要がある（1目標はEXAM/READINGいずれか一方のため、goal.materialsと
    goal.bookは常にどちらか一方のみ実データを持つ）。daily_recordは日付単位で他goalの
    実績・日記と共存しうるため、対象ログ削除後に完全に空（他goalのstudy_log・
    reading_log・chat_message・record_comment・日記本文のいずれも無い）になったものだけを
    追加で削除し、他goalのデータは保持する。
    """
    material_ids = [m.id for m in goal.materials]
    study_logs = session.query(StudyLog).filter(StudyLog.material_id.in_(material_ids)).all()
    book_ids = [goal.book.id] if goal.book is not None else []
    reading_logs = session.query(ReadingLog).filter(ReadingLog.book_id.in_(book_ids)).all()
    diary_entries = session.query(DailyGoalDiary).filter(DailyGoalDiary.goal_id == goal.id).all()
    if not study_logs and not reading_logs and not diary_entries:
        return
    record_ids = (
        {log.daily_record_id for log in study_logs}
        | {log.daily_record_id for log in reading_logs}
        | {entry.daily_record_id for entry in diary_entries}
    )
    for log in study_logs:
        session.delete(log)
    for log in reading_logs:
        session.delete(log)
    for entry in diary_entries:
        session.delete(entry)
    session.flush()

    remaining_log_counts = dict(
        session.query(StudyLog.daily_record_id, func.count(StudyLog.id))
        .filter(StudyLog.daily_record_id.in_(record_ids))
        .group_by(StudyLog.daily_record_id)
        .all()
    )
    remaining_reading_log_counts = dict(
        session.query(ReadingLog.daily_record_id, func.count(ReadingLog.id))
        .filter(ReadingLog.daily_record_id.in_(record_ids))
        .group_by(ReadingLog.daily_record_id)
        .all()
    )
    chat_counts = dict(
        session.query(ChatMessage.daily_record_id, func.count(ChatMessage.id))
        .filter(ChatMessage.daily_record_id.in_(record_ids))
        .group_by(ChatMessage.daily_record_id)
        .all()
    )
    comment_counts = dict(
        session.query(RecordComment.daily_record_id, func.count(RecordComment.id))
        .filter(RecordComment.daily_record_id.in_(record_ids))
        .group_by(RecordComment.daily_record_id)
        .all()
    )
    remaining_diary_counts = dict(
        session.query(DailyGoalDiary.daily_record_id, func.count(DailyGoalDiary.id))
        .filter(DailyGoalDiary.daily_record_id.in_(record_ids))
        .group_by(DailyGoalDiary.daily_record_id)
        .all()
    )
    records = session.query(DailyRecord).filter(DailyRecord.id.in_(record_ids)).all()
    for record in records:
        if remaining_log_counts.get(record.id, 0) > 0:
            continue
        if remaining_reading_log_counts.get(record.id, 0) > 0:
            continue
        if chat_counts.get(record.id, 0) > 0 or comment_counts.get(record.id, 0) > 0:
            continue
        if remaining_diary_counts.get(record.id, 0) > 0:
            continue
        session.delete(record)
    session.flush()


def delete_archived_goal(session: Session, goal: Goal, *, cascade_study_logs: bool) -> None:
    """アーカイブ済み目標を完全削除する（物理削除、仕様書7.1.1、データ構造編4.2）。

    cascade_study_logs=Falseの場合、実績(study_log、読書目標はreading_log)が1件でも
    残る教材・書籍があれば削除全体を拒否する（material→study_log・book→reading_logの
    通常のRESTRICT挙動のまま）。
    """
    if goal.archived_at is None:
        raise InvalidStateTransitionError("アーカイブ済みの目標のみ完全削除できます")

    if cascade_study_logs:
        _cascade_delete_activity_logs(session, goal)
    else:
        material_ids = [m.id for m in goal.materials]
        offending = (
            session.query(StudyLog.material_id)
            .filter(StudyLog.material_id.in_(material_ids))
            .first()
        )
        if offending is not None:
            raise MaterialHasStudyLogsError(offending[0])
        if goal.book is not None:
            offending_reading_log = (
                session.query(ReadingLog.book_id)
                .filter(ReadingLog.book_id == goal.book.id)
                .first()
            )
            if offending_reading_log is not None:
                raise BookHasReadingLogsError(offending_reading_log[0])

    session.delete(goal)
    session.flush()


def activate_goal(session: Session, goal: Goal) -> Goal:
    """下書き→進行中（仕様書7.1）。前提未達・リソース超過時は例外を送出する。

    読書目標（category=READING）は書籍の登録のみを前提とし、教材・リソース配分・
    計画基準値（EXAM固有の計画管理、要件定義書R-71）は対象外とする。
    """
    if goal.status != GoalStatus.DRAFT:
        raise InvalidStateTransitionError("下書き状態の目標のみ開始できます")

    if goal.category == GoalCategory.READING:
        if goal.book is None:
            raise ValidationError("書籍を登録してください")
    else:
        if not goal.exam_subjects:
            raise ExamSubjectRequiredError
        if not goal.materials:
            raise MaterialRequiredError
        if goal.resource_ratio <= 0:
            raise ResourceRatioRequiredError
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
    """一時停止→進行中（仕様書7.1）。リソースの空きが不足する場合はエラーとする。

    読書目標（category=READING）はリソース配分プールの対象外（要件定義書R-64）で
    resource_ratioが常に0のため、この検証を適用しない（activate_goalと同じ扱い）。
    """
    if goal.status != GoalStatus.PAUSED:
        raise InvalidStateTransitionError("一時停止中の目標のみ復帰できます")
    if goal.category == GoalCategory.EXAM:
        if goal.resource_ratio <= 0:
            raise ResourceRatioRequiredError
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
