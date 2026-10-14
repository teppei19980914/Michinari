"""日次記録のCRUD・報告確定・カレンダー表示用データの取得（設計書データ構造編5.4・6.2、
仕様書6.4〜6.7・7.2・14章、実装フェーズ分割計画書Phase4）。

Phase4時点ではAI連携（chat_message の生成）は対象外としていた。報告確定は chat_message が
空の状態でも成立する（実装フェーズ分割計画書Phase4「注意点」、AI呼び出し失敗時の動作保証
16.7）。chat_message自体の生成・保存はapp/services/daily_feedback_service.py（Phase5）が
担い、本ファイルは日次記録（DailyRecord）の取得・作成のためのヘルパのみ提供する。

本モジュールは、目標の種類（資格試験・読書・仕事）を問わず2カテゴリ以上から参照される
共通処理を置く（実装フェーズ分割計画書S02、`record_service.py`からの分割）。カテゴリ固有の
処理は`record_service_exam.py`・`record_service_reading.py`・`record_service_work.py`に
分割して置く。
"""

import datetime as dt
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import func, or_
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql.elements import ColumnElement

from app.constants.enums import DayType, GoalCategory, RecordState
from app.models.base import utcnow
from app.models.record import (
    ChatMessage,
    DailyGoalDiary,
    DailyRecord,
    ReadingLog,
    ReadingLogSlotTime,
    RecordComment,
    StudyLogSlotTime,
    WorkLog,
)
from app.models.resource import ResourceSlot
from app.services import calendar_service, goal_service
from app.services.exceptions import (
    BackdateLimitExceededError,
    ImmutableRecordError,
    NotFoundError,
    ValidationError,
)

if TYPE_CHECKING:  # pragma: no cover (型チェック専用、実行時には到達しない)
    from app.services.record_service_exam import StudyLogItem
    from app.services.record_service_reading import ReadingLogItem
    from app.services.record_service_work import WorkLogItem


def get_daily_record(session: Session, target_date: dt.date) -> DailyRecord | None:
    """指定日の日次記録を取得する。未入力の日は None を返す（例外にしない）。"""
    return session.query(DailyRecord).filter(DailyRecord.record_date == target_date).first()


def ensure_daily_record(session: Session, target_date: dt.date) -> DailyRecord:
    """指定日の日次記録を取得し、なければ空のPROGRESS_ONLYレコードを作成する。

    AI対話（Phase5 POST /records/{date}/chat）は実績・日記の確定前でも実行できるため、
    chat_messageのFK先として空の日次記録を先に確保する用途で使う。
    """
    return get_daily_record(session, target_date) or _create_record(session, target_date)


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


#: 時間枠別の投下時間（slot_id → 分）。仕様書6.5「時間枠ごとの投下時間の入力」。
SlotMinutes = dict[int, int]


def _validate_slot_minutes(session: Session, slot_minutes: SlotMinutes) -> SlotMinutes:
    """時間枠別入力を検証し、0分の行を除いた辞書を返す（データ構造編5.4「0分の入力は
    行を作らない」）。配分していないスロットの指定も許容する（仕様書6.5）。"""
    positive: SlotMinutes = {}
    for slot_id, minutes in slot_minutes.items():
        if minutes < 0:
            raise ValidationError("Minutes spent must be zero or more")
        if minutes == 0:
            continue
        if session.get(ResourceSlot, slot_id) is None:
            raise ValidationError("Specified resource slot does not exist")
        positive[slot_id] = minutes
    return positive


def _total_minutes(slot_minutes: SlotMinutes) -> int | None:
    """時間枠別入力の合計。1件も入力が無い場合は「未入力」を表すNoneとする。

    0ではなくNoneとするのは、投下時間が未入力の実績を実効速度の算出から除外するため
    （ロジック・プロンプト編8.4、仕様書6.6）。
    """
    return sum(slot_minutes.values()) or None


def _replace_slot_times(
    session: Session,
    model: type[StudyLogSlotTime] | type[ReadingLogSlotTime],
    owner_column: InstrumentedAttribute,
    owner_id: int,
    slot_minutes: SlotMinutes,
) -> None:
    """時間枠別の内訳を入れ替える（学習実績・読書記録で共通、CLAUDE.md DRYの原則）。

    合計（minutes_spent）の更新経路を呼び出し元のupsert1箇所に限定することで、内訳との
    不整合を防ぐ（データ構造編5.4）。
    """
    session.query(model).filter(owner_column == owner_id).delete()
    session.flush()
    for slot_id in sorted(slot_minutes):
        session.add(
            model(
                **{owner_column.key: owner_id},
                slot_id=slot_id,
                minutes=slot_minutes[slot_id],
            )
        )
    session.flush()


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


def resolve_record_state(record: DailyRecord | None) -> RecordState | None:
    """日次記録から、カレンダー・ダッシュボード表示用の単一状態を求める。

    「行が無ければ未入力、あれば3カテゴリを集約する」という展開が、カレンダー・
    ダッシュボード・本日取得・記録リマインドの4箇所へ写されていたためここへ集約する
    （CLAUDE.md DRYの原則）。カテゴリが増えたとき（実際にPhase13で読書、Phase19で仕事が
    増えている）に直す箇所を1つにするのが狙い。

    引数:
        record: 対象日の日次記録。未入力の日は None。

    返り値:
        集約した確定状態。触れたカテゴリが1つも無ければ None。

    使用例:
        >>> resolve_record_state(None) is None
        True
    """
    if record is None:
        return None
    return aggregate_record_state(
        record.exam_record_state, record.reading_record_state, record.work_record_state
    )


def count_reported_records_before(
    session: Session, category: GoalCategory, before_date: dt.date
) -> int:
    """指定日より前に、そのカテゴリで確定済み(REPORTED)の記録が何件あるかを返す
    （観点提案プロンプトの閾値判定、S-4 4-3。記録がまだ少ない学習者にAIが断定的な
    分析をしないよう、日次報告フィードバックへ条件付きで追加指示を注入するために使う）。
    """
    column = category_state_column(category)
    return (
        session.query(func.count(DailyRecord.id))
        .filter(DailyRecord.record_date < before_date, column == RecordState.REPORTED)
        .scalar()
    )


def has_any_reported_record(session: Session) -> bool:
    """一度でも確定済み(REPORTED)の記録があるかを返す（初回記録バナーの非表示条件、S-4 4-2）。

    カテゴリを問わず1件でもREPORTEDがあればTrue。バナーの表示・非表示を
    `location.state`のような遷移1回限りの状態ではなく、実データ（記録確定という
    ドメインイベント）に紐づけるために追加した。
    """
    exists = (
        session.query(DailyRecord.id)
        .filter(
            or_(
                DailyRecord.exam_record_state == RecordState.REPORTED,
                DailyRecord.reading_record_state == RecordState.REPORTED,
                DailyRecord.work_record_state == RecordState.REPORTED,
            )
        )
        .first()
    )
    return exists is not None


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
        raise ValidationError("Cannot finalize a report for a future date")
    if target_date < today - dt.timedelta(days=1):
        raise BackdateLimitExceededError(target_date, today)


def register_progress(
    session: Session,
    target_date: dt.date,
    items: "list[StudyLogItem]",
    today: dt.date,
    reading_items: "list[ReadingLogItem] | None" = None,
    work_items: "list[WorkLogItem] | None" = None,
) -> DailyRecord:
    """進捗のみ登録する（未入力→進捗のみ登録済、または既存の進捗のみ登録済の更新）。

    入力可能期間は「対象日が当日または前日以前」（仕様書7.2）であり、未来日は拒否する。
    study_logs・reading_logs・work_logsの少なくとも1つに1件以上の入力を要求する
    （いずれも空の登録は無意味なため。特定の1つのみ必須にできないのは、資格試験・読書・
    仕事の目標が同時進行しうるため）。ガード・状態更新は入力があったカテゴリのみに適用する
    （他カテゴリが確定済みでも、そのカテゴリに入力が無ければ影響しない。仕様変更2026-09-05）。

    カテゴリ別の実際の適用（ログの反映＋状態更新）は`record_service_exam`/
    `record_service_reading`/`record_service_work`の`apply_progress`へ委譲する。
    本関数側でこれら3モジュールを先頭でimportすると、各モジュールが本モジュールの
    `_set_category_state`等を先頭でimportしているため循環importになる。呼び出し時
    （本関数が実際に呼ばれる時点では3モジュールとも読み込み済み）まで遅延させて
    importすることで回避する（実装フェーズ分割計画書S02）。
    """
    from app.services import record_service_exam, record_service_reading, record_service_work

    reading_items = reading_items or []
    work_items = work_items or []
    if target_date > today:
        raise ValidationError("Cannot register progress for a future date")
    if not items and not reading_items and not work_items:
        raise ValidationError("Enter at least one progress record")

    record = get_daily_record(session, target_date)
    if items:
        _ensure_category_not_reported(record, target_date, GoalCategory.EXAM)
    if reading_items:
        _ensure_category_not_reported(record, target_date, GoalCategory.READING)
    if work_items:
        _ensure_category_not_reported(record, target_date, GoalCategory.WORK)

    record = record or _create_record(session, target_date)
    record_service_exam.apply_progress(session, record, items)
    record_service_reading.apply_progress(session, record, reading_items)
    record_service_work.apply_progress(session, record, work_items)
    session.flush()
    return record


def get_comment(session: Session, comment_id: int) -> RecordComment:
    comment = session.get(RecordComment, comment_id)
    if comment is None:
        raise NotFoundError("RecordComment", comment_id)
    return comment


def add_comment(session: Session, target_date: dt.date, body: str) -> RecordComment:
    """コメントを追加する。コメント対象の日次記録が存在しない場合はNOT_FOUNDとする。"""
    goal_service.ensure_any_goal_active(session)
    record = get_daily_record(session, target_date)
    if record is None:
        raise NotFoundError("DailyRecord", target_date)
    comment = RecordComment(daily_record_id=record.id, body=body)
    session.add(comment)
    session.flush()
    return comment


def update_comment(session: Session, comment: RecordComment, body: str) -> RecordComment:
    goal_service.ensure_any_goal_active(session)
    comment.body = body
    session.flush()
    return comment


def delete_comment(session: Session, comment: RecordComment) -> None:
    goal_service.ensure_any_goal_active(session)
    session.delete(comment)
    session.flush()


@dataclass(frozen=True)
class PreviousEntry:
    """「前回の記録」ヒント表示用（仕様書6.5、記録画面改善タスク2026-09-17）。

    記述欄の上部に「前回はこう書いていました」として提示するための、対象日より前で
    直近の記録日・本文を持つ。空文字/NULLの記録（想起・業務記録は必須入力だが、日記は
    任意のため空でも行が存在しうる）は「前回」として提示する意味がないため対象から除く。
    """

    record_date: dt.date
    body: str


def _get_previous_entry(
    session: Session,
    model: type[DailyGoalDiary] | type[ReadingLog] | type[WorkLog],
    owner_column: InstrumentedAttribute,
    owner_id: int,
    body_column: InstrumentedAttribute | ColumnElement[str],
    before_date: dt.date,
) -> PreviousEntry | None:
    """対象日より前で本文のある直近1件を取得する共通実装。

    日記（目標別）・想起記録（書籍別）・業務記録（案件別）は「所有者列で絞り込み、
    対象日より前で直近の1件を取る」という同型のクエリが3回必要になるため共通化する
    （CODING_RULES.md「①DRYの原則」、_replace_slot_timesと同じ考え方）。
    """
    row = (
        session.query(DailyRecord.record_date, body_column)
        .join(model, model.daily_record_id == DailyRecord.id)
        .filter(
            owner_column == owner_id,
            DailyRecord.record_date < before_date,
            body_column.isnot(None),
            body_column != "",
        )
        .order_by(DailyRecord.record_date.desc())
        .first()
    )
    return PreviousEntry(record_date=row[0], body=row[1]) if row else None


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
