"""ヘルプAIアシスタントのAPI（Phase43、仕様書6.18・8.1 AI-14、データ構造編6.2）。

質問の受付と、画面が使う上限の取得だけを担う。質疑の処理そのものは
`services/help_assistant_service.py` に置く（API層はドメイン例外を HTTP へ変換するのみ、
CODING_RULES.md・開発Todo B-10）。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.app_setting_keys import AI_HELP_QUESTION_MAX_CHARS
from app.database import get_db
from app.schemas.help_assistant import (
    HelpAssistantAnswerRead,
    HelpAssistantLimitsRead,
    HelpAssistantQuestionRequest,
    HelpSectionRef,
)
from app.services import help_assistant_service, setting_reader
from app.services.help_content import load_sections

router = APIRouter(tags=["help-assistant"])


@router.post("/help-assistant/questions", response_model=HelpAssistantAnswerRead)
def ask_question(
    payload: HelpAssistantQuestionRequest, session: Session = Depends(get_db)
) -> HelpAssistantAnswerRead:
    """質問に、ヘルプ本文に基づいて答える（質問ごとのチャットで送信し、回答後に削除する）。"""
    answer = help_assistant_service.ask(session, raw_question=payload.question)
    titles = {section.id: section.title for section in load_sections()}
    return HelpAssistantAnswerRead(
        status=answer.status,
        answer=answer.text or None,
        sections=[
            HelpSectionRef(id=section_id, title=titles[section_id])
            for section_id in answer.section_ids
        ],
    )


@router.get("/help-assistant/limits", response_model=HelpAssistantLimitsRead)
def get_limits(session: Session = Depends(get_db)) -> HelpAssistantLimitsRead:
    """質問の上限文字数を返す（入力欄の文字数表示と事前チェックに使う）。"""
    return HelpAssistantLimitsRead(
        max_question_chars=setting_reader.get_int(session, AI_HELP_QUESTION_MAX_CHARS)
    )
