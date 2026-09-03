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
    ReadingLogInput,
    ReadingLogRead,
    StudyLogInput,
    StudyLogRead,
    TodayRead,
)
from app.services import (
    daily_feedback_service,
    goal_service,
    reading_feedback_service,
    record_service,
)
from app.services.record_service import DiaryEntryItem, ReadingLogItem, StudyLogItem

router = APIRouter(tags=["records"])


def _to_study_log_items(inputs: list[StudyLogInput]) -> list[StudyLogItem]:
    return [
        StudyLogItem(
            material_id=item.material_id,
            minutes_spent=item.minutes_spent,
            amount_completed=item.amount_completed,
            cycle_number=item.cycle_number,
            quality_value=item.quality_value,
        )
        for item in inputs
    ]


def _to_reading_log_items(inputs: list[ReadingLogInput]) -> list[ReadingLogItem]:
    return [
        ReadingLogItem(
            book_id=item.book_id,
            recall_body=item.recall_body,
            pages_read=item.pages_read,
            current_page=item.current_page,
        )
        for item in inputs
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
        record_state=record.record_state if record else None,
        diary_entries=[
            DiaryEntryRead(
                goal_id=entry.goal_id,
                goal_name=entry.goal_name,
                diary_body=entry.diary_body,
                diary_learned=entry.diary_learned,
            )
            for entry in diary_entries
        ],
        reported_at=record.reported_at if record else None,
        study_logs=[
            StudyLogRead.model_validate(log) for log in (record.study_logs if record else [])
        ],
        reading_logs=[
            ReadingLogRead.model_validate(log) for log in (record.reading_logs if record else [])
        ],
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
    """論理的な本日の日付と記録状態を取得する（クライアント側でシステム日付から判断しない）。"""
    today = goal_service.resolve_today(session)
    record = record_service.get_daily_record(session, today)
    return TodayRead(logical_date=today, record_state=record.record_state if record else None)


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
    )
    session.commit()
    return _serialize_record(session, target_date, record)


@router.post("/records/{target_date}/finalize", response_model=DailyRecordRead)
def finalize_record(
    target_date: dt.date, payload: FinalizeRequest, session: Session = Depends(get_db)
) -> DailyRecordRead:
    today = goal_service.resolve_today(session)
    record = record_service.finalize_record(
        session,
        target_date,
        _to_study_log_items(payload.study_logs),
        _to_diary_entry_items(payload.diary_entries),
        today,
        _to_reading_log_items(payload.reading_logs),
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
