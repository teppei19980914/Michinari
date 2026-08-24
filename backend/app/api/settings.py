"""アプリ設定・プロンプトテンプレートのAPI（データ構造編6.2、仕様書6.11、
実装フェーズ分割計画書Phase7）。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.enums import AiPurpose
from app.database import get_db
from app.models.setting import PromptTemplate
from app.schemas.setting import (
    AiConnectionSettingsRead,
    AppSettingsRead,
    AppSettingsUpdate,
    DisplaySettingsRead,
    LogSettingsRead,
    PromptDegradationSettingsRead,
    PromptTemplateRead,
    PromptTemplateUpdate,
    ThresholdSettingsRead,
)
from app.services import settings_service
from app.services.exceptions import NotFoundError

router = APIRouter(tags=["settings"])


def _serialize_settings(settings: settings_service.AppSettings) -> AppSettingsRead:
    return AppSettingsRead(
        ai_connection=AiConnectionSettingsRead(**vars(settings.ai_connection)),
        threshold=ThresholdSettingsRead(**vars(settings.threshold)),
        prompt_degradation=PromptDegradationSettingsRead(**vars(settings.prompt_degradation)),
        display=DisplaySettingsRead(**vars(settings.display)),
        log=LogSettingsRead(**vars(settings.log)),
    )


def _serialize_prompt_template(template: PromptTemplate) -> PromptTemplateRead:
    return PromptTemplateRead(
        purpose=AiPurpose(template.purpose),
        body=template.body,
        is_customized=template.is_customized,
    )


def _resolve_purpose(purpose: str) -> AiPurpose:
    try:
        return AiPurpose(purpose)
    except ValueError as exc:
        raise NotFoundError("プロンプトテンプレート", purpose) from exc


@router.get("/settings", response_model=AppSettingsRead)
def get_settings(session: Session = Depends(get_db)) -> AppSettingsRead:
    return _serialize_settings(settings_service.get_app_settings(session))


@router.patch("/settings", response_model=AppSettingsRead)
def update_settings(
    payload: AppSettingsUpdate, session: Session = Depends(get_db)
) -> AppSettingsRead:
    groups = payload.model_dump(exclude_unset=True)
    updated = settings_service.update_app_settings(
        session,
        ai_connection=groups.get("ai_connection"),
        threshold=groups.get("threshold"),
        prompt_degradation=groups.get("prompt_degradation"),
        display=groups.get("display"),
        log=groups.get("log"),
    )
    session.commit()
    return _serialize_settings(updated)


@router.get("/prompt-templates", response_model=list[PromptTemplateRead])
def list_prompt_templates(session: Session = Depends(get_db)) -> list[PromptTemplateRead]:
    return [_serialize_prompt_template(t) for t in settings_service.list_prompt_templates(session)]


@router.patch("/prompt-templates/{purpose}", response_model=PromptTemplateRead)
def update_prompt_template(
    purpose: str, payload: PromptTemplateUpdate, session: Session = Depends(get_db)
) -> PromptTemplateRead:
    template = settings_service.update_prompt_template(
        session, _resolve_purpose(purpose), payload.body
    )
    session.commit()
    return _serialize_prompt_template(template)


@router.post("/prompt-templates/{purpose}/reset", response_model=PromptTemplateRead)
def reset_prompt_template(purpose: str, session: Session = Depends(get_db)) -> PromptTemplateRead:
    template = settings_service.reset_prompt_template(session, _resolve_purpose(purpose))
    session.commit()
    return _serialize_prompt_template(template)
