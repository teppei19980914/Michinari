"""日次記録のCRUD・報告確定・カレンダー表示用データの取得（設計書データ構造編5.4・6.2、
仕様書6.4〜6.7・7.2・14章、実装フェーズ分割計画書Phase4）。

AI連携（chat_message の生成）は本フェーズの対象外とする。報告確定は chat_message が
空の状態で成立させる（実装フェーズ分割計画書Phase4「注意点」）。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from app.constants.enums import DayType, GoalStatus, QualityMetricType, RecordState
from app.models.base import utcnow
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, RecordComment, StudyLog
from app.services import calendar_service, cycle_service, goal_service, quota_service
from app.services.exceptions import (
    BackdateLimitExceededError,
    ImmutableRecordError,
    NotFoundError,
    ValidationError,
)

#: 主観的手応え（1〜5）→ 品質指標（20〜100）の変換表（ロジック・プロンプト編14.1）。
_SUBJECTIVE_QUALITY_MAP: dict[int, float] = {1: 20.0, 2: 40.0, 3: 60.0, 4: 80.0, 5: 100.0}


def get_daily_record(session: Session, target_date: dt.date) -> DailyRecord | None:
    """指定日の日次記録を取得する。未入力の日は None を返す（例外にしない）。"""
    return session.query(DailyRecord).filter(DailyRecord.record_date == target_date).first()


def _normalize_quality(material: Material, raw: float | None) -> float | None:
    """品質指標を保存値へ正規化する（ロジック・プロンプト編14.1）。"""
    if raw is None:
        return None
    if material.quality_metric_type == QualityMetricType.NONE:
        raise ValidationError("品質指標を設定していない教材には品質値を入力できません")
    if material.quality_metric_type == QualityMetricType.SUBJECTIVE:
        if raw != int(raw) or int(raw) not in _SUBJECTIVE_QUALITY_MAP:
            raise ValidationError("主観的手応えは1〜5の整数で入力してください")
        return _SUBJECTIVE_QUALITY_MAP[int(raw)]
    # OBJECTIVE / SELF_SCORED（仕様書10章: 品質指標は0〜100）
    if not (0 <= raw <= 100):
        raise ValidationError("品質指標は0〜100の範囲で入力してください")
    return float(raw)


def _load_materials(session: Session, material_ids: set[int]) -> dict[int, Material]:
    if not material_ids:
        return {}
    materials = session.query(Material).filter(Material.id.in_(material_ids)).all()
    found = {m.id: m for m in materials}
    missing = material_ids - set(found)
    if missing:
        raise NotFoundError("教材", sorted(missing))
    return found


@dataclass(frozen=True)
class StudyLogItem:
    """学習実績の登録入力（API層のスキーマから変換して渡す）。"""

    material_id: int
    minutes_spent: int | None
    amount_completed: float
    cycle_number: int | None
    quality_value: float | None


def _upsert_study_log(
    session: Session, daily_record: DailyRecord, material: Material, item: StudyLogItem
) -> StudyLog:
    quality = _normalize_quality(material, item.quality_value)
    cycle_number = item.cycle_number
    if cycle_number is None:
        # 周回番号の既定値は算出値（現在周回）とする（Phase4完了条件）。
        cycle_number = cycle_service.get_material_progress(session, material).current_cycle

    study_log = (
        session.query(StudyLog)
        .filter(StudyLog.daily_record_id == daily_record.id, StudyLog.material_id == material.id)
        .first()
    )
    if study_log is None:
        study_log = StudyLog(daily_record_id=daily_record.id, material_id=material.id)
        session.add(study_log)
    study_log.minutes_spent = item.minutes_spent
    study_log.amount_completed = item.amount_completed
    study_log.cycle_number = cycle_number
    study_log.quality_value = quality
    session.flush()
    return study_log


def _apply_study_logs(
    session: Session, daily_record: DailyRecord, items: list[StudyLogItem]
) -> None:
    materials = _load_materials(session, {item.material_id for item in items})
    for item in items:
        _upsert_study_log(session, daily_record, materials[item.material_id], item)


def _create_record(session: Session, target_date: dt.date) -> DailyRecord:
    """新規の日次記録を作成する。呼び出し側は事前に get_daily_record で不在を確認済み。"""
    record = DailyRecord(record_date=target_date, record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    return record


def _ensure_not_reported(record: DailyRecord | None, target_date: dt.date) -> None:
    """確定済み(REPORTED)記録への更新を拒否する（register_progress/finalize_record共通、仕様書7.2）。"""
    if record is not None and record.record_state == RecordState.REPORTED:
        raise ImmutableRecordError(target_date)


def register_progress(
    session: Session,
    target_date: dt.date,
    items: list[StudyLogItem],
    today: dt.date,
) -> DailyRecord:
    """進捗のみ登録する（未入力→進捗のみ登録済、または既存の進捗のみ登録済の更新）。

    入力可能期間は「対象日が当日または前日以前」（仕様書7.2）であり、未来日は拒否する。
    """
    if target_date > today:
        raise ValidationError("未来日への実績登録はできません")

    record = get_daily_record(session, target_date)
    _ensure_not_reported(record, target_date)

    record = record or _create_record(session, target_date)
    _apply_study_logs(session, record, items)
    return record


def finalize_record(
    session: Session,
    target_date: dt.date,
    items: list[StudyLogItem],
    diary_body: str,
    diary_learned: str,
    today: dt.date,
) -> DailyRecord:
    """報告を確定する（未入力/進捗のみ登録済 → 報告済）。

    入力可能期間は「対象日が当日または前日」（仕様書7.2）に限られる。「前日」の判定は
    today（呼び出し側が1日の境界時刻を考慮して算出した論理的な本日）を基準とする。
    """
    if target_date > today:
        raise ValidationError("未来日の報告確定はできません")

    record = get_daily_record(session, target_date)
    _ensure_not_reported(record, target_date)
    if target_date < today - dt.timedelta(days=1):
        raise BackdateLimitExceededError(target_date, today)

    record = record or _create_record(session, target_date)
    _apply_study_logs(session, record, items)
    record.diary_body = diary_body
    record.diary_learned = diary_learned
    record.record_state = RecordState.REPORTED
    record.reported_at = utcnow()
    session.flush()
    return record


def get_comment(session: Session, comment_id: int) -> RecordComment:
    comment = session.get(RecordComment, comment_id)
    if comment is None:
        raise NotFoundError("コメント", comment_id)
    return comment


def add_comment(session: Session, target_date: dt.date, body: str) -> RecordComment:
    """コメントを追加する。コメント対象の日次記録が存在しない場合はNOT_FOUNDとする。"""
    record = get_daily_record(session, target_date)
    if record is None:
        raise NotFoundError("日次記録", target_date)
    comment = RecordComment(daily_record_id=record.id, body=body)
    session.add(comment)
    session.flush()
    return comment


def update_comment(session: Session, comment: RecordComment, body: str) -> RecordComment:
    comment.body = body
    session.flush()
    return comment


def delete_comment(session: Session, comment: RecordComment) -> None:
    session.delete(comment)
    session.flush()


@dataclass(frozen=True)
class QuotaItem:
    """指定日の教材別日次ノルマ（データ構造編6.2 GET /records/{date}/quota）。"""

    material_id: int
    material_name: str
    current_cycle: int
    planned_cycles: int
    daily_quota: float


def compute_daily_quota(session: Session, target_date: dt.date) -> list[QuotaItem]:
    """進行中の全教材について、当日締切前の教材の日次ノルマを算出する（仕様書6.5）。"""
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    # material.goal を後段でgoalの参照に使うため joinedload で事前取得する（N+1禁止、CLAUDE.md）。
    materials = (
        session.query(Material)
        .join(Goal, Material.goal_id == Goal.id)
        .options(joinedload(Material.goal))
        .filter(
            Goal.status == GoalStatus.ACTIVE,
            Material.is_active.is_(True),
            Material.due_date >= target_date,
        )
        .all()
    )
    results = []
    for material in materials:
        progress = cycle_service.get_material_progress(session, material)
        daily_quota = quota_service.compute_material_quota(
            session, material.goal, material, target_date, treat_holiday_as_buffer
        )
        results.append(
            QuotaItem(
                material_id=material.id,
                material_name=material.name,
                current_cycle=progress.current_cycle,
                planned_cycles=material.planned_cycles,
                daily_quota=daily_quota,
            )
        )
    return results


@dataclass(frozen=True)
class CalendarDayView:
    """カレンダー1日分の表示情報（データ構造編6.2 GET /calendar）。"""

    target_date: dt.date
    day_type: DayType
    record_state: RecordState | None


def get_calendar_days(
    session: Session, date_from: dt.date, date_to: dt.date
) -> list[CalendarDayView]:
    """期間内の日種別と記録状態をまとめて取得する。期間が逆転している場合は空を返す。"""
    if date_from > date_to:
        return []

    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    day_types = calendar_service.resolve_day_types(
        session, date_from, date_to, treat_holiday_as_buffer
    )
    record_states = dict(
        session.query(DailyRecord.record_date, DailyRecord.record_state)
        .filter(DailyRecord.record_date >= date_from, DailyRecord.record_date <= date_to)
        .all()
    )
    return [
        CalendarDayView(
            target_date=target_date,
            day_type=day_types[target_date],
            record_state=record_states.get(target_date),
        )
        for target_date in sorted(day_types)
    ]
