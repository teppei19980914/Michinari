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
from app.constants.sentinels import UNSET
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
    WorkLog,
)
from app.services import (
    allocation_service,
    baseline_service,
    calendar_service,
    cycle_service,
    quota_service,
    setting_reader,
)
from app.services.exceptions import (
    BookHasReadingLogsError,
    CloseConfirmationRequiredError,
    ExamSubjectRequiredError,
    InvalidStateTransitionError,
    MaterialHasStudyLogsError,
    MaterialRequiredError,
    NotFoundError,
    ResourceAllocationRequiredError,
    ValidationError,
    WorkAssignmentHasWorkLogsError,
)

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


def ensure_goal_active(goal: Goal, *, action_label: str) -> None:
    """進行中（ACTIVE）以外の目標に対する操作を拒否する共通ガード（Phase26）。

    daily_feedback_service／reading_feedback_service／work_feedback_serviceの3ファイルで
    同一のACTIVEチェックが逐語重複していたため、ここへ集約した（CLAUDE.md DRYの原則）。
    action_labelはエラーメッセージに埋め込む操作名（例:「日次報告フィードバック」）。
    """
    if goal.status != GoalStatus.ACTIVE:
        raise InvalidStateTransitionError(f"進行中の目標のみ{action_label}を実行できます")


def _validate_allocation_capacity(session: Session, goal: Goal) -> None:
    """目標の現在の配分が、各スロットの容量に収まることを検証する（データ構造編5.2）。

    開始・復帰の時点で、他のACTIVEな目標の配分と合わせて超過しないかを見る。設定時点では
    ACTIVEでなかった目標（DRAFT・PAUSED）が合計計算に算入されていないため、状態遷移の
    たびに検証し直す必要がある（仕様書7.1）。
    """
    allocation_service.validate_capacity(
        session,
        allocation_service.get_allocation_minutes(session, goal.id),
        exclude_goal_id=goal.id,
    )


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
    memo: str | None = UNSET,
) -> Goal:
    """目標の基本情報を更新する。

    リソース配分は本関数では扱わない（スロット単位の一括更新である
    `PUT /goals/{id}/slot-allocations` → allocation_service.replace_allocations が担う。
    データ構造編6.2）。
    """
    ensure_goal_editable(goal)

    # name・start_dateはNOT NULL列のためNone＝未指定で曖昧さがない。memoはNULL許容のため
    # 「未指定」と「明示的なクリア」を番兵で区別する（constants/sentinels.py）。
    if name is not None:
        goal.name = name
    if start_date is not None:
        goal.start_date = start_date
    if memo is not UNSET:
        goal.memo = memo

    session.flush()
    return goal


def delete_goal(session: Session, goal: Goal) -> None:
    if goal.status != GoalStatus.DRAFT:
        raise InvalidStateTransitionError("下書き状態の目標のみ削除できます")
    if goal.archived_at is not None:
        raise InvalidStateTransitionError(
            "アーカイブ済みの目標は削除できません。復元するか、アーカイブ済み一覧から完全削除してください"
        )
    session.delete(goal)
    session.flush()


def archive_goal(session: Session, goal: Goal) -> Goal:
    """進行中でない目標をアーカイブする（論理削除、仕様書7.1.1）。

    下書き・一時停止・クローズ済みが対象（進行中の目標はアーカイブできない）。
    """
    if goal.status == GoalStatus.ACTIVE:
        raise InvalidStateTransitionError("進行中の目標はアーカイブできません")
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
    work_assignment_ids = [goal.work_assignment.id] if goal.work_assignment is not None else []
    work_logs = (
        session.query(WorkLog).filter(WorkLog.work_assignment_id.in_(work_assignment_ids)).all()
    )
    diary_entries = session.query(DailyGoalDiary).filter(DailyGoalDiary.goal_id == goal.id).all()
    if not study_logs and not reading_logs and not work_logs and not diary_entries:
        return
    record_ids = (
        {log.daily_record_id for log in study_logs}
        | {log.daily_record_id for log in reading_logs}
        | {log.daily_record_id for log in work_logs}
        | {entry.daily_record_id for entry in diary_entries}
    )
    for log in study_logs:
        session.delete(log)
    for log in reading_logs:
        session.delete(log)
    for log in work_logs:
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
    remaining_work_log_counts = dict(
        session.query(WorkLog.daily_record_id, func.count(WorkLog.id))
        .filter(WorkLog.daily_record_id.in_(record_ids))
        .group_by(WorkLog.daily_record_id)
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
        if remaining_work_log_counts.get(record.id, 0) > 0:
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
                session.query(ReadingLog.book_id).filter(ReadingLog.book_id == goal.book.id).first()
            )
            if offending_reading_log is not None:
                raise BookHasReadingLogsError(offending_reading_log[0])
        if goal.work_assignment is not None:
            offending_work_log = (
                session.query(WorkLog.work_assignment_id)
                .filter(WorkLog.work_assignment_id == goal.work_assignment.id)
                .first()
            )
            if offending_work_log is not None:
                raise WorkAssignmentHasWorkLogsError(offending_work_log[0])

    session.delete(goal)
    session.flush()


def activate_goal(session: Session, goal: Goal) -> Goal:
    """下書き→進行中（仕様書7.1）。前提未達・リソース超過時は例外を送出する。

    読書目標（category=READING）は書籍の登録のみを前提とし、教材・リソース配分・
    計画基準値（EXAM固有の計画管理、要件定義書R-71）は対象外とする。仕事目標
    （category=WORK）は案件情報の登録のみを前提とする（要件定義書R-74）。
    """
    if goal.status != GoalStatus.DRAFT:
        raise InvalidStateTransitionError("下書き状態の目標のみ開始できます")
    if goal.archived_at is not None:
        raise InvalidStateTransitionError("アーカイブ済みの目標です。復元してから開始してください")

    if goal.category == GoalCategory.READING:
        if goal.book is None:
            raise ValidationError("書籍を登録してください")
    elif goal.category == GoalCategory.WORK:
        if goal.work_assignment is None:
            raise ValidationError("案件情報を登録してください")
    else:
        if not goal.exam_subjects:
            raise ExamSubjectRequiredError
        if not goal.materials:
            raise MaterialRequiredError
        if allocation_service.sum_allocated_minutes(session, goal.id) <= 0:
            raise ResourceAllocationRequiredError

    # 読書目標は配分が任意（R-64）のため配分の有無は問わないが、配分を持つ場合は
    # 資格試験と同様にスロットの空きを検証する。仕事目標は配分の対象外（R-74）。
    if goal.category != GoalCategory.WORK:
        _validate_allocation_capacity(session, goal)

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

    資格試験目標のみ「配分が1分以上あること」を要求する。読書目標は配分が任意のため
    （要件定義書R-64）、未設定でも復帰できる。ただし配分を持つ場合は、資格試験と同様に
    スロットの空きが足りるかを検証する（仕様書7.1）。仕事目標は配分の対象外（R-74）。
    """
    if goal.status != GoalStatus.PAUSED:
        raise InvalidStateTransitionError("一時停止中の目標のみ復帰できます")
    if goal.archived_at is not None:
        raise InvalidStateTransitionError("アーカイブ済みの目標です。復元してから再開してください")
    if goal.category == GoalCategory.EXAM:
        if allocation_service.sum_allocated_minutes(session, goal.id) <= 0:
            raise ResourceAllocationRequiredError
    if goal.category != GoalCategory.WORK:
        _validate_allocation_capacity(session, goal)
    goal.status = GoalStatus.ACTIVE
    session.flush()
    return goal


def close_goal(
    session: Session,
    goal: Goal,
    *,
    confirm_without_result: bool = False,
    with_result: bool = False,
) -> Goal:
    """進行中→クローズ（仕様書7.1）。

    全科目の受験結果が登録済みなら自動的に「結果あり」でクローズする。
    未登録の科目が残る場合は confirm_without_result=True の明示確認を必須とする。
    総括レポートの生成(AI連携)はPhase10の責務であり、本関数の成否には影響させない。

    読書目標（category=READING）は exam_subjects が常に空のため has_all_results は
    常にFalseとなり、本関数は confirm_without_result=True を要求したうえで
    CLOSED_WITHOUT_RESULT（中断）へ遷移させる（仕様書7.1）。読了（CLOSED_WITH_RESULT）は
    本関数ではなく book_service.complete_book（POST /books/{id}/complete）を用いる。

    確認待ちは CloseConfirmationRequiredError、本当の状態エラーは
    InvalidStateTransitionError と、必ず別の例外にする（理由は前者のdocstringを参照）。

    仕事目標（category=WORK）は exam_subjects の概念自体を持たないため、上記の
    自動判定・confirm_without_resultによる分岐を適用せず、with_resultの指定のみで
    遷移先を決める（with_result=True→CLOSED_WITH_RESULT＝納品等の成果を伴う終了、
    False（既定）→CLOSED_WITHOUT_RESULT＝中止・打ち切り。要件定義書R-72、
    データ構造編6.2）。with_resultはWORK専用のパラメータであり、EXAM/READINGで
    True指定された場合は拒否する。
    """
    if goal.status != GoalStatus.ACTIVE:
        raise InvalidStateTransitionError("進行中の目標のみクローズできます")

    if goal.category == GoalCategory.WORK:
        goal.status = (
            GoalStatus.CLOSED_WITH_RESULT if with_result else GoalStatus.CLOSED_WITHOUT_RESULT
        )
    else:
        if with_result:
            raise ValidationError("with_resultは仕事目標にのみ指定できます")
        has_all_results = bool(goal.exam_subjects) and all(
            subject.exam_result is not None for subject in goal.exam_subjects
        )
        if has_all_results:
            goal.status = GoalStatus.CLOSED_WITH_RESULT
        else:
            if not confirm_without_result:
                raise CloseConfirmationRequiredError
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
