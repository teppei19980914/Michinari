"""日次記録のAPI（データ構造編6.2、実装フェーズ分割計画書Phase4・Phase5）。

AI対話（POST /records/{date}/chat）はPhase5で追加した（daily_feedback_serviceへ委譲する）。
"""

import datetime as dt

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.record import DailyRecord
from app.schemas.record import (
    ChatMessageRead,
    ChatRequest,
    ChatResponse,
    CommentCreate,
    CommentRead,
    CommentUpdate,
    DailyRecordRead,
    DiaryEntryInput,
    DiaryEntryRead,
    FinalizeRequest,
    ProgressRegisterRequest,
    QuotaItemRead,
    ReadingChatRequest,
    ReadingFinalizeRequest,
    ReadingLogInput,
    ReadingLogRead,
    SlotMinutesInput,
    SlotMinutesRead,
    StudyLogInput,
    StudyLogRead,
    TodayRead,
    WorkChatRequest,
    WorkFinalizeRequest,
    WorkLogInput,
    WorkLogRead,
)
from app.services import (
    daily_feedback_service,
    goal_service,
    reading_feedback_service,
    record_service,
    work_feedback_service,
)
from app.services.record_service import DiaryEntryItem, ReadingLogItem, StudyLogItem, WorkLogItem

router = APIRouter(tags=["records"])


def _to_slot_minutes(entries: list[SlotMinutesInput]) -> dict[int, int]:
    """時間枠別入力を slot_id → 分 の辞書へ畳み込む（同一slot_idの重複指定は加算する）。"""
    slot_minutes: dict[int, int] = {}
    for entry in entries:
        slot_minutes[entry.slot_id] = slot_minutes.get(entry.slot_id, 0) + entry.minutes
    return slot_minutes


def _to_study_log_items(inputs: list[StudyLogInput]) -> list[StudyLogItem]:
    return [
        StudyLogItem(
            material_id=item.material_id,
            slot_minutes=_to_slot_minutes(item.slot_minutes),
            amount_completed=item.amount_completed,
            cycle_number=item.cycle_number,
            quality_value=item.quality_value,
        )
        for item in inputs
    ]


def _serialize_slot_minutes(slot_times) -> list[SlotMinutesRead]:
    """時間枠別内訳を表示用に変換する。時間枠が削除済みの行は slot_name を None とする
    （データ構造編5.4、slot_id は ON DELETE SET NULL）。"""
    return [
        SlotMinutesRead(
            slot_id=row.slot_id,
            slot_name=row.slot.name if row.slot_id is not None and row.slot else None,
            minutes=row.minutes,
        )
        for row in sorted(slot_times, key=lambda row: (row.slot_id is None, row.slot_id or 0))
    ]


def _serialize_study_log(log) -> StudyLogRead:
    return StudyLogRead(
        id=log.id,
        material_id=log.material_id,
        minutes_spent=log.minutes_spent,
        slot_minutes=_serialize_slot_minutes(log.slot_times),
        amount_completed=log.amount_completed,
        cycle_number=log.cycle_number,
        quality_value=log.quality_value,
    )


def _serialize_reading_log(log) -> ReadingLogRead:
    return ReadingLogRead(
        id=log.id,
        book_id=log.book_id,
        recall_body=log.recall_body,
        minutes_spent=log.minutes_spent,
        slot_minutes=_serialize_slot_minutes(log.slot_times),
        pages_read=log.pages_read,
        current_page=log.current_page,
    )


def _to_reading_log_items(inputs: list[ReadingLogInput]) -> list[ReadingLogItem]:
    return [
        ReadingLogItem(
            book_id=item.book_id,
            recall_body=item.recall_body,
            slot_minutes=_to_slot_minutes(item.slot_minutes),
            pages_read=item.pages_read,
            current_page=item.current_page,
        )
        for item in inputs
    ]


def _to_work_log_items(inputs: list[WorkLogInput]) -> list[WorkLogItem]:
    return [
        WorkLogItem(work_assignment_id=item.work_assignment_id, body=item.body) for item in inputs
    ]


def _to_diary_entry_items(inputs: list[DiaryEntryInput]) -> list[DiaryEntryItem]:
    return [
        DiaryEntryItem(
            goal_id=item.goal_id, diary_body=item.diary_body, diary_learned=item.diary_learned
        )
        for item in inputs
    ]


def _serialize_record(
    session: Session, target_date: dt.date, record: DailyRecord | None
) -> DailyRecordRead:
    """未入力の日は record=None として、空の構造を返す（CLAUDE.md: 未入力は例外ではない）。"""
    diary_entries = record_service.get_diary_entries(session, record) if record else []
    return DailyRecordRead(
        record_date=target_date,
        exam_record_state=record.exam_record_state if record else None,
        exam_reported_at=record.exam_reported_at if record else None,
        reading_record_state=record.reading_record_state if record else None,
        reading_reported_at=record.reading_reported_at if record else None,
        work_record_state=record.work_record_state if record else None,
        work_reported_at=record.work_reported_at if record else None,
        diary_entries=[
            DiaryEntryRead(
                goal_id=entry.goal_id,
                goal_name=entry.goal_name,
                diary_body=entry.diary_body,
                diary_learned=entry.diary_learned,
            )
            for entry in diary_entries
        ],
        study_logs=[_serialize_study_log(log) for log in (record.study_logs if record else [])],
        reading_logs=[
            _serialize_reading_log(log) for log in (record.reading_logs if record else [])
        ],
        work_logs=[WorkLogRead.model_validate(log) for log in (record.work_logs if record else [])],
        comments=[CommentRead.model_validate(c) for c in (record.comments if record else [])],
        chat_messages=[
            ChatMessageRead.model_validate(chat_message)
            for chat_message in sorted(
                (record.chat_messages if record else []),
                key=lambda chat_message: chat_message.sequence,
            )
        ],
    )


@router.get("/records/today", response_model=TodayRead)
def get_today(session: Session = Depends(get_db)) -> TodayRead:
    """論理的な本日の日付と記録状態を取得する（クライアント側でシステム日付から判断しない）。

    record_state はカテゴリ横断の集約値（record_service.aggregate_record_state）であり、
    カレンダー・ダッシュボードの単一状態表示にのみ使う（仕様変更2026-09-05）。
    """
    today = goal_service.resolve_today(session)
    record = record_service.get_daily_record(session, today)
    aggregate_state = (
        record_service.aggregate_record_state(
            record.exam_record_state, record.reading_record_state, record.work_record_state
        )
        if record
        else None
    )
    return TodayRead(logical_date=today, record_state=aggregate_state)


@router.get("/records/{target_date}", response_model=DailyRecordRead)
def get_record(target_date: dt.date, session: Session = Depends(get_db)) -> DailyRecordRead:
    record = record_service.get_daily_record(session, target_date)
    return _serialize_record(session, target_date, record)


@router.post("/records/{target_date}/progress", response_model=DailyRecordRead)
def register_progress(
    target_date: dt.date, payload: ProgressRegisterRequest, session: Session = Depends(get_db)
) -> DailyRecordRead:
    today = goal_service.resolve_today(session)
    record = record_service.register_progress(
        session,
        target_date,
        _to_study_log_items(payload.study_logs),
        today,
        _to_reading_log_items(payload.reading_logs),
        _to_work_log_items(payload.work_logs),
    )
    session.commit()
    return _serialize_record(session, target_date, record)


@router.post("/records/{target_date}/finalize", response_model=DailyRecordRead)
def finalize_record(
    target_date: dt.date, payload: FinalizeRequest, session: Session = Depends(get_db)
) -> DailyRecordRead:
    """資格勉強（EXAM）の報告を確定する。読書・仕事の確定状態には影響しない
    （仕様変更2026-09-05: カテゴリごとに独立して確定できるようにするため）。
    """
    today = goal_service.resolve_today(session)
    record = record_service.finalize_record(
        session,
        target_date,
        _to_study_log_items(payload.study_logs),
        _to_diary_entry_items(payload.diary_entries),
        today,
    )
    session.commit()
    return _serialize_record(session, target_date, record)


@router.post("/records/{target_date}/reading-finalize", response_model=DailyRecordRead)
def finalize_reading_record(
    target_date: dt.date, payload: ReadingFinalizeRequest, session: Session = Depends(get_db)
) -> DailyRecordRead:
    """読書の報告を確定する。資格勉強・仕事の確定状態には影響しない
    （既存の `/chat`, `/reading-chat`, `/work-chat` と同じカテゴリ別命名規則）。
    """
    today = goal_service.resolve_today(session)
    record = record_service.finalize_reading_record(
        session, target_date, _to_reading_log_items(payload.reading_logs), today
    )
    session.commit()
    return _serialize_record(session, target_date, record)


@router.post("/records/{target_date}/work-finalize", response_model=DailyRecordRead)
def finalize_work_record(
    target_date: dt.date, payload: WorkFinalizeRequest, session: Session = Depends(get_db)
) -> DailyRecordRead:
    """仕事の報告を確定する。資格勉強・読書の確定状態には影響しない。"""
    today = goal_service.resolve_today(session)
    record = record_service.finalize_work_record(
        session, target_date, _to_work_log_items(payload.work_logs), today
    )
    session.commit()
    return _serialize_record(session, target_date, record)


@router.post("/records/{target_date}/chat", response_model=ChatResponse)
def chat(
    target_date: dt.date, payload: ChatRequest, session: Session = Depends(get_db)
) -> ChatResponse:
    """AI対話を1往復実行する（データ構造編6.2）。実績・日記はこのリクエストの下書き値を
    使うのみで確定させない（AI呼び出し失敗時も入力を失わない、16.7）。
    """
    today = goal_service.resolve_today(session)
    outcome = daily_feedback_service.send_daily_feedback(
        session,
        goal_id=payload.goal_id,
        target_date=target_date,
        today=today,
        message=payload.message,
        study_log_items=_to_study_log_items(payload.study_logs),
        diary_entries=_to_diary_entry_items(payload.diary_entries),
    )
    session.commit()
    return ChatResponse(
        record=_serialize_record(session, target_date, outcome.daily_record),
        assistant_message=ChatMessageRead.model_validate(outcome.assistant_message),
        was_truncated=outcome.was_truncated,
    )


@router.post("/records/{target_date}/reading-chat", response_model=ChatResponse)
def reading_chat(
    target_date: dt.date, payload: ReadingChatRequest, session: Session = Depends(get_db)
) -> ChatResponse:
    """読書目標のAI対話を1往復実行する（データ構造編6.2）。用途と日付ごとに会話を分離する
    既存方針（ロジック・プロンプト編16.3）に従い、資格試験の`/chat`とは独立した会話・
    プロンプト（DAILY_FEEDBACK_READING）として扱う。
    """
    today = goal_service.resolve_today(session)
    outcome = reading_feedback_service.send_reading_feedback(
        session,
        goal_id=payload.goal_id,
        target_date=target_date,
        today=today,
        message=payload.message,
        reading_log_items=_to_reading_log_items(payload.reading_logs),
    )
    session.commit()
    return ChatResponse(
        record=_serialize_record(session, target_date, outcome.daily_record),
        assistant_message=ChatMessageRead.model_validate(outcome.assistant_message),
        was_truncated=outcome.was_truncated,
    )


@router.post("/records/{target_date}/work-chat", response_model=ChatResponse)
def work_chat(
    target_date: dt.date, payload: WorkChatRequest, session: Session = Depends(get_db)
) -> ChatResponse:
    """仕事目標のAI対話を1往復実行する（データ構造編6.2）。用途と日付ごとに会話を分離する
    既存方針（ロジック・プロンプト編16.3）に従い、資格試験の`/chat`・読書の`/reading-chat`
    とは独立した会話・プロンプト（DAILY_FEEDBACK_WORK）として扱う。
    """
    today = goal_service.resolve_today(session)
    outcome = work_feedback_service.send_work_feedback(
        session,
        goal_id=payload.goal_id,
        target_date=target_date,
        today=today,
        message=payload.message,
        work_log_items=_to_work_log_items(payload.work_logs),
    )
    session.commit()
    return ChatResponse(
        record=_serialize_record(session, target_date, outcome.daily_record),
        assistant_message=ChatMessageRead.model_validate(outcome.assistant_message),
        was_truncated=outcome.was_truncated,
    )


@router.get("/records/{target_date}/quota", response_model=list[QuotaItemRead])
def get_quota(target_date: dt.date, session: Session = Depends(get_db)) -> list[QuotaItemRead]:
    items = record_service.compute_daily_quota(session, target_date)
    return [
        QuotaItemRead(
            material_id=item.material_id,
            material_name=item.material_name,
            unit_label=item.unit_label,
            current_cycle=item.current_cycle,
            planned_cycles=item.planned_cycles,
            daily_quota=item.daily_quota,
            quality_metric_type=item.quality_metric_type,
            goal_id=item.goal_id,
            goal_name=item.goal_name,
        )
        for item in items
    ]


@router.post(
    "/records/{target_date}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    target_date: dt.date, payload: CommentCreate, session: Session = Depends(get_db)
) -> CommentRead:
    comment = record_service.add_comment(session, target_date, payload.body)
    session.commit()
    return CommentRead.model_validate(comment)


@router.patch("/comments/{comment_id}", response_model=CommentRead)
def update_comment(
    comment_id: int, payload: CommentUpdate, session: Session = Depends(get_db)
) -> CommentRead:
    comment = record_service.get_comment(session, comment_id)
    record_service.update_comment(session, comment, payload.body)
    session.commit()
    return CommentRead.model_validate(comment)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, session: Session = Depends(get_db)) -> None:
    comment = record_service.get_comment(session, comment_id)
    record_service.delete_comment(session, comment)
    session.commit()
