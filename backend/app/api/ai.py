"""AI連携のAPI（データ構造編6.2、実装フェーズ分割計画書Phase5）。

プロンプト対話そのもの（POST /records/{date}/chat）はapp/api/records.pyに置く
（日次記録に対する操作のため）。本ファイルは認証状態・アシスタント一覧・今日の一言など、
AI基盤そのものに関する操作を担う。
"""

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai import auth as ai_auth
from app.ai import client as ai_client
from app.database import get_db
from app.schemas.ai import AiAssistantRead, AiLoginRequest, AiLoginResult, AiStatusRead
from app.schemas.record import DailyMessageRead
from app.services import daily_message_service, goal_service, settings_service

router = APIRouter(tags=["ai"])


@router.get("/ai/status", response_model=AiStatusRead)
def get_ai_status(session: Session = Depends(get_db)) -> AiStatusRead:
    snapshot = ai_auth.get_status(session)
    return AiStatusRead(
        authenticated=snapshot.authenticated,
        model_status=snapshot.model_status,
        login_in_progress=snapshot.login_in_progress,
    )


@router.post("/ai/login", response_model=AiLoginResult)
def login(payload: AiLoginRequest, session: Session = Depends(get_db)) -> AiLoginResult:
    """PAT指定時は即時反映・確認する。未指定時はフォールバック認証を非同期に開始する（16.2）。

    Hostが指定された場合は設定画面の値（app_setting）にも反映する。認証操作で入力した値が
    設定画面の表示と食い違わないようにするため（設定画面の保存ボタンとは別経路のため）。
    """
    if payload.host:
        settings_service.update_app_settings(session, ai_connection={"host": payload.host})
        session.commit()

    if payload.personal_access_token:
        authenticated = ai_auth.register_pat(
            session, host=payload.host, personal_access_token=payload.personal_access_token
        )
        return AiLoginResult(
            status="AUTHENTICATED" if authenticated else "PENDING", authenticated=authenticated
        )

    ai_auth.start_fallback_login(session)
    return AiLoginResult(status="PENDING", authenticated=False)


@router.post("/ai/logout", status_code=204)
def logout(session: Session = Depends(get_db)) -> None:
    ai_auth.logout(session)


@router.get("/ai/assistants", response_model=list[AiAssistantRead])
def get_assistants(session: Session = Depends(get_db)) -> list[AiAssistantRead]:
    assistants = ai_client.get_assistants(session)
    return [
        AiAssistantRead(
            uid=str(item.get("uid")),
            name=str(item.get("name", "")),
            description=item.get("description"),
        )
        for item in assistants
    ]


@router.get("/daily-message", response_model=list[DailyMessageRead])
def get_daily_message(session: Session = Depends(get_db)) -> list[DailyMessageRead]:
    """今日の一言を目標ごとに取得する。未生成の目標があれば生成する（データ構造編6.2）。"""
    today: dt.date = goal_service.resolve_today(session)
    daily_messages = daily_message_service.get_or_generate(session, today)
    session.commit()
    return [
        DailyMessageRead(
            target_date=message.target_date,
            goal_id=message.goal_id,
            goal_name=message.goal.name if message.goal is not None else None,
            body=message.body,
            generated_at=message.generated_at,
        )
        for message in daily_messages
    ]
