"""カレンダーのAPI（データ構造編6.2、実装フェーズ分割計画書Phase4）。"""

import datetime as dt

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.calendar import CalendarDayRead, DayTypeOverrideRequest, HolidayImportResultRead
from app.services import calendar_service, record_service

router = APIRouter(tags=["calendar"])


@router.get("/calendar", response_model=list[CalendarDayRead])
def get_calendar(
    date_from: dt.date, date_to: dt.date, session: Session = Depends(get_db)
) -> list[CalendarDayRead]:
    days = record_service.get_calendar_days(session, date_from, date_to)
    return [
        CalendarDayRead(
            target_date=day.target_date, day_type=day.day_type, record_state=day.record_state
        )
        for day in days
    ]


@router.put("/calendar/{target_date}/day-type", response_model=CalendarDayRead)
def set_day_type(
    target_date: dt.date, payload: DayTypeOverrideRequest, session: Session = Depends(get_db)
) -> CalendarDayRead:
    calendar_service.set_day_type_override(session, target_date, payload.day_type, payload.note)
    session.commit()
    record = record_service.get_daily_record(session, target_date)
    return CalendarDayRead(
        target_date=target_date,
        day_type=payload.day_type,
        record_state=(
            record_service.aggregate_record_state(
                record.exam_record_state, record.reading_record_state, record.work_record_state
            )
            if record
            else None
        ),
    )


@router.delete("/calendar/{target_date}/day-type", status_code=status.HTTP_204_NO_CONTENT)
def clear_day_type(target_date: dt.date, session: Session = Depends(get_db)) -> None:
    calendar_service.clear_day_type_override(session, target_date)
    session.commit()


@router.post("/calendar/holidays/import", response_model=HolidayImportResultRead)
async def import_holidays(
    file: UploadFile = File(...), session: Session = Depends(get_db)
) -> HolidayImportResultRead:
    content = await file.read()
    result = calendar_service.import_holidays(session, content)
    session.commit()
    return HolidayImportResultRead(
        imported_count=result.imported_count, year_from=result.year_from, year_to=result.year_to
    )
