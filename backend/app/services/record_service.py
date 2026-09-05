"""日次記録のCRUD・報告確定・カレンダー表示用データの取得（設計書データ構造編5.4・6.2、
仕様書6.4〜6.7・7.2・14章、実装フェーズ分割計画書Phase4）。

Phase4時点ではAI連携（chat_message の生成）は対象外としていた。報告確定は chat_message が
空の状態でも成立する（実装フェーズ分割計画書Phase4「注意点」、AI呼び出し失敗時の動作保証
16.7）。chat_message自体の生成・保存はapp/services/daily_feedback_service.py（Phase5）が
担い、本ファイルは日次記録（DailyRecord）の取得・作成のためのヘルパのみ提供する。
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import InstrumentedAttribute, Session, joinedload

from app.constants.enums import DayType, GoalCategory, GoalStatus, QualityMetricType, RecordState
from app.models.base import utcnow
from app.models.book import Book
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import (
    ChatMessage,
    DailyGoalDiary,
    DailyRecord,
    ReadingLog,
    RecordComment,
    StudyLog,
    WorkLog,
)
from app.models.work import WorkAssignment
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


def ensure_daily_record(session: Session, target_date: dt.date) -> DailyRecord:
    """指定日の日次記録を取得し、なければ空のPROGRESS_ONLYレコードを作成する。

    AI対話（Phase5 POST /records/{date}/chat）は実績・日記の確定前でも実行できるため、
    chat_messageのFK先として空の日次記録を先に確保する用途で使う。
    """
    return get_daily_record(session, target_date) or _create_record(session, target_date)


def load_materials_by_id(session: Session, material_ids: set[int]) -> dict[int, Material]:
    """教材IDの集合からMaterialを一括取得する（AI連携のプロンプト組み立てで使用、Phase5）。"""
    return _load_materials(session, material_ids)


def load_books_by_id(session: Session, book_ids: set[int]) -> dict[int, Book]:
    """書籍IDの集合からBookを一括取得する（AI連携のプロンプト組み立てで使用、Phase16）。"""
    return _load_books(session, book_ids)


def load_work_assignments_by_id(
    session: Session, work_assignment_ids: set[int]
) -> dict[int, WorkAssignment]:
    """案件情報IDの集合からWorkAssignmentを一括取得する（AI連携のプロンプト組み立てで
    使用、Phase22）。"""
    return _load_work_assignments(session, work_assignment_ids)


def next_chat_sequence(session: Session, daily_record_id: int) -> int:
    """chat_messageの次のsequence値を返す。用途（purpose）を問わず日次記録全体で採番を
    共有し、表示上の時系列順序が用途を跨いで一貫するようにする（Phase16、モデルのdocstring
    参照）。対話履歴（{{conversation_history}}）への注入時のpurpose絞り込みとは別の関心事。
    """
    current_max = (
        session.query(func.max(ChatMessage.sequence))
        .filter(ChatMessage.daily_record_id == daily_record_id)
        .scalar()
    )
    return (current_max or 0) + 1


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


def _load_goals(session: Session, goal_ids: set[int]) -> dict[int, Goal]:
    if not goal_ids:
        return {}
    goals = session.query(Goal).filter(Goal.id.in_(goal_ids)).all()
    found = {g.id: g for g in goals}
    missing = goal_ids - set(found)
    if missing:
        raise NotFoundError("目標", sorted(missing))
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


@dataclass(frozen=True)
class ReadingLogItem:
    """読書記録の登録入力（API層のスキーマから変換して渡す。study_logの読書版）。"""

    book_id: int
    recall_body: str
    pages_read: int | None
    current_page: int | None


def _load_books(session: Session, book_ids: set[int]) -> dict[int, Book]:
    if not book_ids:
        return {}
    books = session.query(Book).filter(Book.id.in_(book_ids)).all()
    found = {b.id: b for b in books}
    missing = book_ids - set(found)
    if missing:
        raise NotFoundError("書籍", sorted(missing))
    return found


def _upsert_reading_log(
    session: Session, daily_record: DailyRecord, book: Book, item: ReadingLogItem
) -> ReadingLog:
    reading_log = (
        session.query(ReadingLog)
        .filter(ReadingLog.daily_record_id == daily_record.id, ReadingLog.book_id == book.id)
        .first()
    )
    if reading_log is None:
        reading_log = ReadingLog(daily_record_id=daily_record.id, book_id=book.id)
        session.add(reading_log)
    reading_log.recall_body = item.recall_body
    reading_log.pages_read = item.pages_read
    reading_log.current_page = item.current_page
    session.flush()
    return reading_log


def _apply_reading_logs(
    session: Session, daily_record: DailyRecord, items: list[ReadingLogItem]
) -> None:
    books = _load_books(session, {item.book_id for item in items})
    for item in items:
        _upsert_reading_log(session, daily_record, books[item.book_id], item)


@dataclass(frozen=True)
class WorkLogItem:
    """業務記録の登録入力（API層のスキーマから変換して渡す。study_logの仕事版。
    読書と異なりページ数等の付随フィールドは持たない、自由記述1本）。"""

    work_assignment_id: int
    body: str


def _load_work_assignments(
    session: Session, work_assignment_ids: set[int]
) -> dict[int, WorkAssignment]:
    if not work_assignment_ids:
        return {}
    work_assignments = (
        session.query(WorkAssignment).filter(WorkAssignment.id.in_(work_assignment_ids)).all()
    )
    found = {w.id: w for w in work_assignments}
    missing = work_assignment_ids - set(found)
    if missing:
        raise NotFoundError("案件情報", sorted(missing))
    return found


def _upsert_work_log(
    session: Session, daily_record: DailyRecord, work_assignment: WorkAssignment, item: WorkLogItem
) -> WorkLog:
    work_log = (
        session.query(WorkLog)
        .filter(
            WorkLog.daily_record_id == daily_record.id,
            WorkLog.work_assignment_id == work_assignment.id,
        )
        .first()
    )
    if work_log is None:
        work_log = WorkLog(daily_record_id=daily_record.id, work_assignment_id=work_assignment.id)
        session.add(work_log)
    work_log.body = item.body
    session.flush()
    return work_log


def _apply_work_logs(session: Session, daily_record: DailyRecord, items: list[WorkLogItem]) -> None:
    work_assignments = _load_work_assignments(session, {item.work_assignment_id for item in items})
    for item in items:
        _upsert_work_log(session, daily_record, work_assignments[item.work_assignment_id], item)


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


def _create_record(session: Session, target_date: dt.date) -> DailyRecord:
    """新規の日次記録を作成する。呼び出し側は事前に get_daily_record で不在を確認済み。

    確定状態はカテゴリごとに独立しており、どのカテゴリもまだ操作していないため
    3カテゴリともNULL（未着手）のまま作成する。
    """
    record = DailyRecord(record_date=target_date)
    session.add(record)
    session.flush()
    return record


#: カテゴリ別の確定状態列（*_record_state）へのマッピング（DRYの原則、CLAUDE.md）。
#: SQLフィルタ（metrics_service等）と属性の読み書き（本モジュール）の両方で使う。
_CATEGORY_STATE_ATTR: dict[GoalCategory, InstrumentedAttribute] = {
    GoalCategory.EXAM: DailyRecord.exam_record_state,
    GoalCategory.READING: DailyRecord.reading_record_state,
    GoalCategory.WORK: DailyRecord.work_record_state,
}
_CATEGORY_REPORTED_AT_ATTR: dict[GoalCategory, str] = {
    GoalCategory.EXAM: "exam_reported_at",
    GoalCategory.READING: "reading_reported_at",
    GoalCategory.WORK: "work_reported_at",
}


def category_state_column(category: GoalCategory) -> InstrumentedAttribute:
    """目標カテゴリに対応する確定状態列を返す（SQLフィルタで使用、metrics_service等）。"""
    return _CATEGORY_STATE_ATTR[category]


def _get_category_state(record: DailyRecord, category: GoalCategory) -> RecordState | None:
    return getattr(record, _CATEGORY_STATE_ATTR[category].key)


def _set_category_state(record: DailyRecord, category: GoalCategory, state: RecordState) -> None:
    setattr(record, _CATEGORY_STATE_ATTR[category].key, state)
    if state == RecordState.REPORTED:
        setattr(record, _CATEGORY_REPORTED_AT_ATTR[category], utcnow())


def aggregate_record_state(
    exam_state: RecordState | None,
    reading_state: RecordState | None,
    work_state: RecordState | None,
) -> RecordState | None:
    """3カテゴリの確定状態から、カレンダー・ダッシュボード表示用の単一状態を算出する。

    その日一度も操作していないカテゴリ（NULL）は判定から除外する（触れていないカテゴリが
    確定のブロッカーにならないようにするため。仕様変更2026-09-05）。触れたカテゴリが
    1つも無ければNULL（未入力）、1つでもPROGRESS_ONLYがあればPROGRESS_ONLY、触れた
    カテゴリが全てREPORTEDならREPORTED。
    """
    touched = [state for state in (exam_state, reading_state, work_state) if state is not None]
    if not touched:
        return None
    if all(state == RecordState.REPORTED for state in touched):
        return RecordState.REPORTED
    return RecordState.PROGRESS_ONLY


def _ensure_category_not_reported(
    record: DailyRecord | None, target_date: dt.date, category: GoalCategory
) -> None:
    """確定済み(REPORTED)カテゴリへの更新を拒否する（register_progress/finalize_*共通、
    仕様書7.2）。他カテゴリが確定済みでも、対象カテゴリが未確定なら更新できる
    （仕様変更2026-09-05: カテゴリごとに独立して確定できるようにする）。
    """
    if record is not None and _get_category_state(record, category) == RecordState.REPORTED:
        raise ImmutableRecordError(target_date, category)


def _ensure_finalizable_date(target_date: dt.date, today: dt.date) -> None:
    """報告確定の対象日が入力可能期間内（当日または前日）であることを確認する（仕様書7.2）。
    「前日」の判定はtoday（呼び出し側が1日の境界時刻を考慮して算出した論理的な本日）を
    基準とする。finalize_record/finalize_reading_record/finalize_work_record共通。
    """
    if target_date > today:
        raise ValidationError("未来日の報告確定はできません")
    if target_date < today - dt.timedelta(days=1):
        raise BackdateLimitExceededError(target_date, today)


def register_progress(
    session: Session,
    target_date: dt.date,
    items: list[StudyLogItem],
    today: dt.date,
    reading_items: list[ReadingLogItem] | None = None,
    work_items: list[WorkLogItem] | None = None,
) -> DailyRecord:
    """進捗のみ登録する（未入力→進捗のみ登録済、または既存の進捗のみ登録済の更新）。

    入力可能期間は「対象日が当日または前日以前」（仕様書7.2）であり、未来日は拒否する。
    study_logs・reading_logs・work_logsの少なくとも1つに1件以上の入力を要求する
    （いずれも空の登録は無意味なため。特定の1つのみ必須にできないのは、資格試験・読書・
    仕事の目標が同時進行しうるため）。ガード・状態更新は入力があったカテゴリのみに適用する
    （他カテゴリが確定済みでも、そのカテゴリに入力が無ければ影響しない。仕様変更2026-09-05）。
    """
    reading_items = reading_items or []
    work_items = work_items or []
    if target_date > today:
        raise ValidationError("未来日への実績登録はできません")
    if not items and not reading_items and not work_items:
        raise ValidationError("実績を1件以上入力してください")

    record = get_daily_record(session, target_date)
    if items:
        _ensure_category_not_reported(record, target_date, GoalCategory.EXAM)
    if reading_items:
        _ensure_category_not_reported(record, target_date, GoalCategory.READING)
    if work_items:
        _ensure_category_not_reported(record, target_date, GoalCategory.WORK)

    record = record or _create_record(session, target_date)
    if items:
        _apply_study_logs(session, record, items)
        if _get_category_state(record, GoalCategory.EXAM) is None:
            _set_category_state(record, GoalCategory.EXAM, RecordState.PROGRESS_ONLY)
    if reading_items:
        _apply_reading_logs(session, record, reading_items)
        if _get_category_state(record, GoalCategory.READING) is None:
            _set_category_state(record, GoalCategory.READING, RecordState.PROGRESS_ONLY)
    if work_items:
        _apply_work_logs(session, record, work_items)
        if _get_category_state(record, GoalCategory.WORK) is None:
            _set_category_state(record, GoalCategory.WORK, RecordState.PROGRESS_ONLY)
    session.flush()
    return record


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


def finalize_reading_record(
    session: Session,
    target_date: dt.date,
    items: list[ReadingLogItem],
    today: dt.date,
) -> DailyRecord:
    """読書の報告を確定する（未入力/進捗のみ登録済 → 報告済）。

    資格勉強・仕事の確定状態には影響しない（仕様変更2026-09-05）。
    """
    record = get_daily_record(session, target_date)
    _ensure_category_not_reported(record, target_date, GoalCategory.READING)
    _ensure_finalizable_date(target_date, today)

    record = record or _create_record(session, target_date)
    _apply_reading_logs(session, record, items)
    _set_category_state(record, GoalCategory.READING, RecordState.REPORTED)
    session.flush()
    return record


def finalize_work_record(
    session: Session,
    target_date: dt.date,
    items: list[WorkLogItem],
    today: dt.date,
) -> DailyRecord:
    """仕事の報告を確定する（未入力/進捗のみ登録済 → 報告済）。

    資格勉強・読書の確定状態には影響しない（仕様変更2026-09-05）。
    """
    record = get_daily_record(session, target_date)
    _ensure_category_not_reported(record, target_date, GoalCategory.WORK)
    _ensure_finalizable_date(target_date, today)

    record = record or _create_record(session, target_date)
    _apply_work_logs(session, record, items)
    _set_category_state(record, GoalCategory.WORK, RecordState.REPORTED)
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
    category_states = {
        record_date: aggregate_record_state(exam_state, reading_state, work_state)
        for record_date, exam_state, reading_state, work_state in session.query(
            DailyRecord.record_date,
            DailyRecord.exam_record_state,
            DailyRecord.reading_record_state,
            DailyRecord.work_record_state,
        ).filter(DailyRecord.record_date >= date_from, DailyRecord.record_date <= date_to)
    }
    return [
        CalendarDayView(
            target_date=target_date,
            day_type=day_types[target_date],
            record_state=category_states.get(target_date),
        )
        for target_date in sorted(day_types)
    ]
