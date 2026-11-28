"""「今日」の論理日（開発Todo_Web公開_v1.0 D-09、単位2）。

クライアント側では論理日を判断しない。ログイン中のアカウントであることのみ要求する
（論理日自体はアカウントに依存しないサーバ共通の値、D-09・`app/services/calendar_service.py`）。
"""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_account
from app.config import get_settings
from app.models.account import PublishAccount
from app.services import calendar_service

router = APIRouter(prefix="/today", tags=["today"])


class TodayResponse(BaseModel):
    logical_date: date


@router.get("", response_model=TodayResponse)
def get_today(_account: PublishAccount = Depends(get_current_account)) -> TodayResponse:
    settings = get_settings()
    return TodayResponse(logical_date=calendar_service.resolve_today(settings.today_boundary_hour))
