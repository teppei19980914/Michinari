"""日次記録のうち資格試験（EXAM）固有の処理（設計書データ構造編5.4・6.2、
仕様書6.4〜6.7・7.2・14章）。共通処理は`record_service_common.py`を参照（実装フェーズ
分割計画書S02、`record_service.py`からの分割）。
"""

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy.orm import Session, joinedload

from app.constants.enums import GoalCategory, GoalStatus, QualityMetricType, RecordState
from app.constants.goal_transitions import GoalOperation
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import (
    DailyGoalDiary,
    DailyRecord,
    StudyLog,
    StudyLogSlotTime,
    diary_text_expr,
)
from app.services import (
    allocation_service,
    cycle_service,
    goal_service,
    quota_service,
    slot_service,
    speed_service,
)
from app.services.exceptions import NotFoundError, ValidationError
from app.services.record_service_common import (
    PreviousEntry,
    SlotMinutes,
    _create_record,
    _ensure_category_not_reported,
    _ensure_finalizable_date,
    _get_category_state,
    _get_previous_entry,
    _replace_slot_times,
    _set_category_state,
    _total_minutes,
    _validate_slot_minutes,
    get_daily_record,
)

#: 主観的手応え（1〜5）→ 品質指標（20〜100）の変換表（ロジック・プロンプト編14.1）。
_SUBJECTIVE_QUALITY_MAP: dict[int, float] = {1: 20.0, 2: 40.0, 3: 60.0, 4: 80.0, 5: 100.0}


def load_materials_by_id(session: Session, material_ids: set[int]) -> dict[int, Material]:
    """教材IDの集合からMaterialを一括取得する（AI連携のプロンプト組み立てで使用、Phase5）。"""
    return _load_materials(session, material_ids)


def _normalize_quality(material: Material, raw: float | None) -> float | None:
    """品質指標を保存値へ正規化する（ロジック・プロンプト編14.1）。"""
    if raw is None:
        return None
    if material.quality_metric_type == QualityMetricType.NONE:
        raise ValidationError(
            "Cannot enter a quality value for a material with no quality metric configured"
        )
    if material.quality_metric_type == QualityMetricType.SUBJECTIVE:
        if raw != int(raw) or int(raw) not in _SUBJECTIVE_QUALITY_MAP:
            raise ValidationError("Subjective score must be an integer between 1 and 5")
        return _SUBJECTIVE_QUALITY_MAP[int(raw)]
    # OBJECTIVE / SELF_SCORED（仕様書10章: 品質指標は0〜100）
    if not (0 <= raw <= 100):
        raise ValidationError("Quality value must be between 0 and 100")
    return float(raw)


def _load_materials(session: Session, material_ids: set[int]) -> dict[int, Material]:
    if not material_ids:
        return {}
    materials = session.query(Material).filter(Material.id.in_(material_ids)).all()
    found = {m.id: m for m in materials}
    missing = material_ids - set(found)
    if missing:
        raise NotFoundError("Material", sorted(missing))
    return found


def _load_goals(session: Session, goal_ids: set[int]) -> dict[int, Goal]:
    if not goal_ids:
        return {}
    goals = session.query(Goal).filter(Goal.id.in_(goal_ids)).all()
    found = {g.id: g for g in goals}
    missing = goal_ids - set(found)
    if missing:
        raise NotFoundError("Goal", sorted(missing))
    return found


@dataclass(frozen=True)
class StudyLogItem:
    """学習実績の登録入力（API層のスキーマから変換して渡す）。

    投下時間は時間枠ごとに入力され（slot_minutes）、教材の minutes_spent はその合計として
    サービス層が設定する（データ構造編5.4、仕様書6.5）。
    """

    material_id: int
    amount_completed: float
    cycle_number: int | None
    quality_value: float | None
    #: 時間枠が未入力の実績も成立する（投下時間は任意。ロジック・プロンプト編8.4）。
    slot_minutes: SlotMinutes = field(default_factory=dict)


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
    slot_minutes = _validate_slot_minutes(session, item.slot_minutes)
    study_log.minutes_spent = _total_minutes(slot_minutes)
    study_log.amount_completed = item.amount_completed
    study_log.cycle_number = cycle_number
    study_log.quality_value = quality
    session.flush()
    _replace_slot_times(
        session, StudyLogSlotTime, StudyLogSlotTime.study_log_id, study_log.id, slot_minutes
    )
    return study_log


def _apply_study_logs(
    session: Session, daily_record: DailyRecord, items: list[StudyLogItem]
) -> None:
    materials = _load_materials(session, {item.material_id for item in items})
    for material in materials.values():
        goal_service.ensure_operation_allowed(material.goal, GoalOperation.RECORD)
    for item in items:
        _upsert_study_log(session, daily_record, materials[item.material_id], item)


def apply_progress(session: Session, daily_record: DailyRecord, items: list[StudyLogItem]) -> None:
    """`record_service_common.register_progress`から呼ばれる、資格試験（EXAM）分の適用。

    入力が無ければ何もしない（register_progressのディスパッチから無条件に呼ばれるため、
    空リストの早期returnをここで行う。実装フェーズ分割計画書S02、複雑度分割）。
    """
    if not items:
        return
    _apply_study_logs(session, daily_record, items)
    if _get_category_state(daily_record, GoalCategory.EXAM) is None:
        _set_category_state(daily_record, GoalCategory.EXAM, RecordState.PROGRESS_ONLY)


@dataclass(frozen=True)
class DiaryEntryItem:
    """日記（目標別）の登録入力（API層のスキーマから変換して渡す）。"""

    goal_id: int
    diary_body: str
    diary_learned: str


@dataclass(frozen=True)
class DiaryEntry:
    """日記（目標別）の読み取り結果（目標名は表示用に付与、DBには保存しない）。"""

    goal_id: int | None
    goal_name: str | None
    diary_body: str | None
    diary_learned: str | None


def _upsert_diary_entry(
    session: Session, daily_record: DailyRecord, goal: Goal, item: DiaryEntryItem
) -> DailyGoalDiary:
    entry = (
        session.query(DailyGoalDiary)
        .filter(
            DailyGoalDiary.daily_record_id == daily_record.id, DailyGoalDiary.goal_id == goal.id
        )
        .first()
    )
    if entry is None:
        entry = DailyGoalDiary(daily_record_id=daily_record.id, goal_id=goal.id)
        session.add(entry)
    entry.diary_body = item.diary_body
    entry.diary_learned = item.diary_learned
    session.flush()
    return entry


def _apply_diary_entries(
    session: Session, daily_record: DailyRecord, items: list[DiaryEntryItem]
) -> None:
    goals = _load_goals(session, {item.goal_id for item in items})
    for goal in goals.values():
        goal_service.ensure_operation_allowed(goal, GoalOperation.RECORD)
    for item in items:
        _upsert_diary_entry(session, daily_record, goals[item.goal_id], item)


def get_diary_entries(session: Session, daily_record: DailyRecord) -> list[DiaryEntry]:
    """日次記録に紐づく目標別の日記を取得する（compute_daily_quotaと同じくjoinedloadで
    N+1を回避する、CLAUDE.md）。"""
    entries = (
        session.query(DailyGoalDiary)
        .options(joinedload(DailyGoalDiary.goal))
        .filter(DailyGoalDiary.daily_record_id == daily_record.id)
        .all()
    )
    return [
        DiaryEntry(
            goal_id=entry.goal_id,
            goal_name=entry.goal.name if entry.goal else None,
            diary_body=entry.diary_body,
            diary_learned=entry.diary_learned,
        )
        for entry in entries
    ]


def finalize_record(
    session: Session,
    target_date: dt.date,
    items: list[StudyLogItem],
    diary_entries: list[DiaryEntryItem],
    today: dt.date,
) -> DailyRecord:
    """資格勉強（EXAM）の報告を確定する（未入力/進捗のみ登録済 → 報告済）。

    読書・仕事の確定状態には影響しない（仕様変更2026-09-05: カテゴリごとに独立して
    確定できるようにする）。
    """
    record = get_daily_record(session, target_date)
    _ensure_category_not_reported(record, target_date, GoalCategory.EXAM)
    _ensure_finalizable_date(target_date, today)

    record = record or _create_record(session, target_date)
    _apply_study_logs(session, record, items)
    _apply_diary_entries(session, record, diary_entries)
    _set_category_state(record, GoalCategory.EXAM, RecordState.REPORTED)
    session.flush()
    return record


@dataclass(frozen=True)
class SlotDefaultMinutes:
    """日次報告の時間枠別入力欄1つ分の既定値（仕様書6.5「初期値」）。

    9.2の按分結果（計画上その時間枠でその教材に割り当たる分数）をそのまま初期値として
    提示し、実績が異なる場合のみ利用者が上書きする。
    """

    slot_id: int
    slot_name: str
    minutes: int


@dataclass(frozen=True)
class QuotaItem:
    """指定日の教材別日次ノルマ（データ構造編6.2 GET /records/{date}/quota）。

    unit_label・quality_metric_type はSC-06/SC-07の実績入力欄（数量の単位表示、
    品質指標の入力形式切替）に必要なため保持する（仕様書6.5）。
    """

    material_id: int
    material_name: str
    unit_label: str
    current_cycle: int
    planned_cycles: int
    daily_quota: float
    quality_metric_type: QualityMetricType
    goal_id: int
    goal_name: str
    #: 時間枠ごとの投下時間入力欄の既定値（配分済みの枠のみ。仕様書6.5）。
    slot_defaults: list[SlotDefaultMinutes] = field(default_factory=list)


def compute_daily_quota(session: Session, target_date: dt.date) -> list[QuotaItem]:
    """進行中の全教材について、当日が学習期間内（開始日〜締切）の教材の日次ノルマを
    算出する（仕様書6.5）。開始日前の教材は対象外とする（先行着手した実績は日記欄で
    記録する運用とし、ノルマ未算出の状態でSC-06/SC-07/SC-01に混在させない）。
    """
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)
    # material.goal を後段でgoalの参照に使うため joinedload で事前取得する（N+1禁止、CLAUDE.md）。
    materials = (
        session.query(Material)
        .join(Goal, Material.goal_id == Goal.id)
        .options(joinedload(Material.goal))
        .filter(
            Goal.status == GoalStatus.ACTIVE,
            Material.is_active.is_(True),
            Material.start_date <= target_date,
            Material.due_date >= target_date,
        )
        .all()
    )
    slot_defaults = _compute_slot_defaults(session, materials, target_date)
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
                unit_label=material.unit_label,
                current_cycle=progress.current_cycle,
                planned_cycles=material.planned_cycles,
                daily_quota=daily_quota,
                quality_metric_type=material.quality_metric_type,
                goal_id=material.goal_id,
                goal_name=material.goal.name,
                slot_defaults=slot_defaults.get(material.id, []),
            )
        )
    return results


def _compute_slot_defaults(
    session: Session, materials: list[Material], target_date: dt.date
) -> dict[int, list[SlotDefaultMinutes]]:
    """material_id → 時間枠別入力欄の既定値（ロジック・プロンプト編9.2の按分結果）。

    目標ごとに1回だけ按分を算出する（教材ごとに呼ぶとN+1になる。CLAUDE.md
    パフォーマンスチェック）。
    """
    slots = slot_service.get_active_slots(session)
    slot_names = {slot.id: slot.name for slot in slots}
    slots_by_weekday = slot_service.group_slots_by_weekday(slots)

    by_goal: dict[int, list[Material]] = {}
    for material in materials:
        by_goal.setdefault(material.goal_id, []).append(material)

    defaults: dict[int, list[SlotDefaultMinutes]] = {}
    for goal_id, goal_materials in by_goal.items():
        weights = speed_service.compute_weights(session, goal_materials)
        allocation = slot_service.allocate_day(
            weights,
            slots_by_weekday,
            target_date,
            allocation_service.get_allocation_minutes(session, goal_id),
        )
        for slot_id in sorted(allocation):
            for material_id, minutes in allocation[slot_id].items():
                rounded = int(minutes)
                if rounded <= 0:
                    continue
                defaults.setdefault(material_id, []).append(
                    SlotDefaultMinutes(
                        slot_id=slot_id, slot_name=slot_names[slot_id], minutes=rounded
                    )
                )
    return defaults


def get_previous_diary_entry(
    session: Session, goal_id: int, before_date: dt.date
) -> PreviousEntry | None:
    """対象目標について、対象日より前で直近の日記を取得する。

    入力欄の主役は「学んだこと」（diary_learned）のため、それを優先し、未入力の旧データだけ
    従来の本文（diary_body）を使う。
    """
    return _get_previous_entry(
        session,
        DailyGoalDiary,
        DailyGoalDiary.goal_id,
        goal_id,
        diary_text_expr(),
        before_date,
    )
