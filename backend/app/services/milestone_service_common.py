"""節目のお祝い（開発Todo_節目のお祝い_v1.0）の共通処理。

`GoalMilestoneAchievement`のCRUD、`app_setting`閾値の読み出し、3種別共通の節目
（CONSECUTIVE_DAYS/TOTAL_RECORD_DAYS）の判定、未祝い一覧取得、祝い済み更新、
起動時バックフィル（既存利用者の更新直後に大量表示されるのを防ぐ、開発Todo §0 M9）を
担う。種別固有の判定（読書・資格・仕事）は`milestone_service_<category>.py`が持ち、
ここから呼び出す（ディスパッチのみ、個々の判定ロジックはここに書かない）。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.services import milestone_service_reading

from app.constants.app_setting_keys import (
    MILESTONE_BACKFILL_COMPLETED,
    MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS,
    MILESTONE_TOTAL_RECORD_DAYS_THRESHOLDS,
)
from app.constants.enums import GoalCategory, GoalStatus, MilestoneType, RecordState
from app.models.base import utcnow
from app.models.goal import Goal
from app.models.milestone import GoalMilestoneAchievement
from app.models.record import DailyRecord
from app.models.setting import AppSetting
from app.services import metrics_service, record_service_common, setting_reader
from app.services.exceptions import NotFoundError


@dataclass(frozen=True)
class PendingMilestone:
    """未登録の到達節目（判定関数の戻り値。永続化前の値）。"""

    milestone_type: MilestoneType
    milestone_key: str


def _count_total_record_days(session: Session, goal: Goal, today: dt.date) -> int:
    """累計記録日数（`DailyRecord`の当該カテゴリ状態列がREPORTEDの日数）。

    `metrics_service.compute_consecutive_report_days`と同じ「カテゴリ別状態列のみを見る」
    考え方の累計版（開発Todo_節目のお祝い_v1.0 §0 M1）。
    """
    column = record_service_common.category_state_column(goal.category)
    return (
        session.query(DailyRecord.id)
        .filter(
            DailyRecord.record_date >= goal.start_date,
            DailyRecord.record_date <= today,
            column == RecordState.REPORTED,
        )
        .count()
    )


def threshold_milestones(
    session: Session, key: str, current_value: int | float, milestone_type: MilestoneType
) -> list[PendingMilestone]:
    """`current_value`が設定キー`key`（カンマ区切りの閾値一覧）のいずれかの閾値以上であれば、
    該当する閾値ごとに1件返す（種別ごとの判定関数から共通で呼ぶ、CODING_RULES.md①DRYの原則）。
    """
    return [
        PendingMilestone(milestone_type, str(threshold))
        for threshold in setting_reader.get_int_list(session, key)
        if current_value >= threshold
    ]


def detect_common_milestones(
    session: Session, goal: Goal, today: dt.date
) -> list[PendingMilestone]:
    """3種別共通の節目（連続/累計記録日数）を判定する。閾値以上であれば、その閾値ごとに
    1件返す（既に`GoalMilestoneAchievement`にある分の除外は呼び出し元が行う）。
    """
    consecutive_days = metrics_service.compute_consecutive_report_days(
        session, goal, today, treat_holiday_as_buffer=True
    )
    total_record_days = _count_total_record_days(session, goal, today)
    return threshold_milestones(
        session,
        MILESTONE_CONSECUTIVE_DAYS_THRESHOLDS,
        consecutive_days,
        MilestoneType.CONSECUTIVE_DAYS,
    ) + threshold_milestones(
        session,
        MILESTONE_TOTAL_RECORD_DAYS_THRESHOLDS,
        total_record_days,
        MilestoneType.TOTAL_RECORD_DAYS,
    )


def _detect_category_milestones(
    session: Session,
    goal: Goal,
    today: dt.date,
    reading_totals: milestone_service_reading.ReadingTotals | None = None,
) -> list[PendingMilestone]:
    """種別固有の節目判定へディスパッチする（循環importを避けるため関数内でimportする。
    `milestone_service_<category>.py`はいずれも本モジュールの`PendingMilestone`/CRUDに
    依存するため、モジュール先頭でのimportは循環になる）。

    `reading_totals`はREADING種別向けのlifetime集計（累計ページ数・読了冊数、利用者の
    読書全体が対象）の事前計算結果。複数のREADING目標を1回のバッチ処理で判定する
    呼び出し元（`detect_and_record_for_category`・`backfill_achievements_if_needed`）が、
    目標数に関わらず集計を1回だけ行うために渡す（省略時はこの関数が都度算出する）。
    """
    from app.services import (
        milestone_service_exam,
        milestone_service_reading,
        milestone_service_work,
    )

    if goal.category == GoalCategory.EXAM:
        return milestone_service_exam.detect_exam_milestones(session, goal, today)
    if goal.category == GoalCategory.READING:
        return milestone_service_reading.detect_reading_milestones(
            session, goal, today, reading_totals
        )
    return milestone_service_work.detect_work_milestones(session, goal, today)


def _existing_keys(session: Session, goal_id: int, milestone_type: MilestoneType) -> set[str]:
    rows = (
        session.query(GoalMilestoneAchievement.milestone_key)
        .filter(
            GoalMilestoneAchievement.goal_id == goal_id,
            GoalMilestoneAchievement.milestone_type == milestone_type,
        )
        .all()
    )
    return {row[0] for row in rows}


def _record_new_achievements(
    session: Session,
    goal_id: int,
    pending: list[PendingMilestone],
    achieved_at: dt.datetime,
    celebrated_at: dt.datetime | None,
) -> list[GoalMilestoneAchievement]:
    """`pending`のうち未登録のものだけを新規行として追加する（既存行の重複INSERTを
    `UniqueConstraint`より先に避ける）。
    """
    existing_by_type: dict[MilestoneType, set[str]] = {}
    created: list[GoalMilestoneAchievement] = []
    for item in pending:
        existing = existing_by_type.setdefault(
            item.milestone_type, _existing_keys(session, goal_id, item.milestone_type)
        )
        if item.milestone_key in existing:
            continue
        row = GoalMilestoneAchievement(
            goal_id=goal_id,
            milestone_type=item.milestone_type,
            milestone_key=item.milestone_key,
            achieved_at=achieved_at,
            celebrated_at=celebrated_at,
        )
        session.add(row)
        existing.add(item.milestone_key)
        created.append(row)
    if created:
        session.flush()
    return created


def detect_and_record_new_achievements(
    session: Session,
    goal: Goal,
    today: dt.date,
    reading_totals: milestone_service_reading.ReadingTotals | None = None,
) -> list[GoalMilestoneAchievement]:
    """記録確定の直後に呼ぶ（開発Todo_節目のお祝い_v1.0 §4）。新しく到達した節目を
    永続化（`celebrated_at=NULL`）し、作成した行を返す。

    `reading_totals`は`_detect_category_milestones`と同じ（バッチ呼び出し元が複数の
    READING目標にわたる集計を1回だけ行うために渡す。省略時はこの関数が都度算出する）。
    """
    pending = detect_common_milestones(session, goal, today) + _detect_category_milestones(
        session, goal, today, reading_totals
    )
    now = utcnow()
    return _record_new_achievements(session, goal.id, pending, achieved_at=now, celebrated_at=None)


def detect_and_record_for_category(
    session: Session, category: GoalCategory, today: dt.date
) -> None:
    """記録確定（`finalize`系POST）の直後に、そのカテゴリのACTIVE目標すべてについて
    到達判定・永続化を行う（開発Todo_節目のお祝い_v1.0 §4）。

    `DailyRecord`はカテゴリ別の確定状態を日付単位で1行持つのみで目標には紐付かない
    （複数の同カテゴリ目標が同時進行しうる、`app/models/record.py`のDailyRecordの
    docstring参照）ため、確定処理を呼んだ1目標だけでなく同カテゴリの全ACTIVE目標を
    対象にする。戻り値は使わない（新規到達の有無はGETで別途確認する、GETに副作用を
    持たせないため）。

    READINGの場合、累計ページ数・読了冊数（利用者の読書全体が対象のlifetime集計）を
    目標の数だけ繰り返し算出しないよう、ループの前に1回だけ算出して各目標の判定へ渡す
    （performance-reviewer指摘、2026-11-05）。
    """
    from app.services import milestone_service_reading

    goals = (
        session.query(Goal)
        .filter(Goal.category == category, Goal.status == GoalStatus.ACTIVE)
        .all()
    )
    reading_totals = (
        milestone_service_reading.compute_reading_totals(session)
        if category == GoalCategory.READING
        else None
    )
    for goal in goals:
        detect_and_record_new_achievements(session, goal, today, reading_totals)


def list_pending_celebrations(session: Session, goal_id: int) -> list[GoalMilestoneAchievement]:
    """未お祝い（`celebrated_at`がNULL）の節目を到達順に返す（モーダルのキュー表示用）。"""
    return (
        session.query(GoalMilestoneAchievement)
        .filter(
            GoalMilestoneAchievement.goal_id == goal_id,
            GoalMilestoneAchievement.celebrated_at.is_(None),
        )
        .order_by(GoalMilestoneAchievement.achieved_at, GoalMilestoneAchievement.id)
        .all()
    )


def list_achievements(session: Session, goal_id: int) -> list[GoalMilestoneAchievement]:
    """目標の節目履歴を到達の新しい順で返す（分析画面「節目の記録」一覧用）。"""
    return (
        session.query(GoalMilestoneAchievement)
        .filter(GoalMilestoneAchievement.goal_id == goal_id)
        .order_by(GoalMilestoneAchievement.achieved_at.desc(), GoalMilestoneAchievement.id.desc())
        .all()
    )


def mark_celebrated(
    session: Session, goal_id: int, milestone_id: int, now: dt.datetime
) -> GoalMilestoneAchievement:
    """お祝いモーダルを閉じたときに呼ぶ。他の目標の節目IDを指定された場合は404と同様に扱う
    （開発Todo_節目のお祝い_v1.0 STRIDE分析：存在しないIDの指定）。
    """
    row = session.get(GoalMilestoneAchievement, milestone_id)
    if row is None or row.goal_id != goal_id:
        raise NotFoundError("GoalMilestoneAchievement", milestone_id)
    row.celebrated_at = now
    session.flush()
    return row


def backfill_achievements_if_needed(session: Session, today: dt.date) -> None:
    """既存利用者の更新直後に節目のお祝いが大量表示されるのを防ぐ（開発Todo_節目のお祝い_v1.0
    §0 M9）。一度きりのフラグ（`MILESTONE_BACKFILL_COMPLETED`）が立っていれば何もしない。
    立っていなければ、全目標の現在到達済み節目を通常判定と同じ関数で算出し、
    `achieved_at`=`celebrated_at`=現在時刻で登録してフラグを立てる（新規インストールは
    目標0件のため実質無害に完了する）。`app/main.py`の`bootstrap_database`（シード投入の
    直後）から呼ぶ。

    READINGのlifetime集計（累計ページ数・読了冊数）は全目標分をまとめて1回だけ算出する
    （`detect_and_record_for_category`と同じ理由、performance-reviewer指摘2026-11-05）。
    """
    if setting_reader.get_bool(session, MILESTONE_BACKFILL_COMPLETED):
        return

    from app.services import milestone_service_reading

    reading_totals = milestone_service_reading.compute_reading_totals(session)
    now = utcnow()
    for goal in session.query(Goal).all():
        pending = detect_common_milestones(session, goal, today) + _detect_category_milestones(
            session, goal, today, reading_totals
        )
        _record_new_achievements(session, goal.id, pending, achieved_at=now, celebrated_at=now)

    flag_row = session.get(AppSetting, MILESTONE_BACKFILL_COMPLETED)
    if flag_row is None:  # pragma: no cover (起動時シードが必ず先に投入するため到達しない)
        raise NotFoundError("AppSetting", MILESTONE_BACKFILL_COMPLETED)
    flag_row.value = "true"
    session.flush()
