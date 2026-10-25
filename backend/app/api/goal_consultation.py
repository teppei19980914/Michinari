"""目標相談チャットのAPI（S09、要件定義書R-104。S10で読書・仕事へ展開し履歴APIを追加、
S11で会話継続の会話系APIを追加）。

質問の受付・画面が使う上限の取得・相談履歴の一覧/削除・会話の作成/一覧/削除だけを担う。
質疑の処理そのものは`services/goal_consultation_service_common.py`、会話単位の管理は
`services/goal_consultation_conversation_service.py`に置く（API層はドメイン例外をHTTPへ
変換するのみ、CODING_RULES.md、`help_assistant.py`と同じ方針）。対象カテゴリの制限は撤廃した
（S10でEXAM・READING・WORKの全カテゴリを許可、開発Todo v1.1 V1・V9）。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.constants.app_setting_keys import AI_GOAL_CONSULTATION_QUESTION_MAX_CHARS
from app.database import get_db
from app.schemas.goal_consultation import (
    GoalConsultationAnswerRead,
    GoalConsultationCitedWeek,
    GoalConsultationConversationCreateRequest,
    GoalConsultationConversationRead,
    GoalConsultationHistoryItemRead,
    GoalConsultationLimitsRead,
    GoalConsultationQuestionRequest,
)
from app.services import (
    goal_consultation_conversation_service,
    goal_consultation_log_service,
    goal_consultation_service_common,
    goal_service,
    setting_reader,
)

router = APIRouter(tags=["goal-consultation"])


@router.post("/goals/{goal_id}/consultation/questions", response_model=GoalConsultationAnswerRead)
def ask_question(
    goal_id: int, payload: GoalConsultationQuestionRequest, session: Session = Depends(get_db)
) -> GoalConsultationAnswerRead:
    """質問に、目標の記録に基づいて答える（質問ごとのチャットで送信し、回答後に削除する）。

    `conversation_id`がこの目標に属する会話であることを検証してから渡す（`goal_id`との
    二重絞り込み、開発Todo v1.2 §5脅威モデル）。
    """
    goal = goal_service.get_goal(session, goal_id)
    conversation = goal_consultation_conversation_service.get_for_goal(
        session, goal, payload.conversation_id
    )
    today = goal_service.resolve_today(session)
    answer = goal_consultation_service_common.ask(
        session,
        goal=goal,
        today=today,
        conversation_id=conversation.id,
        raw_question=payload.question,
    )
    return GoalConsultationAnswerRead(
        status=answer.status,
        answer=answer.text or None,
        cited_dates=list(answer.cited_dates),
        cited_weeks=[
            GoalConsultationCitedWeek(start=start, end=end) for start, end in answer.cited_weeks
        ],
    )


@router.post(
    "/goals/{goal_id}/consultation/conversations",
    response_model=GoalConsultationConversationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    goal_id: int,
    payload: GoalConsultationConversationCreateRequest,
    session: Session = Depends(get_db),
) -> GoalConsultationConversationRead:
    """新しい会話を開始する（利用者が自由に複数の会話を作れる方式、開発Todo v1.2 確認事項③）。"""
    goal = goal_service.get_goal(session, goal_id)
    entry = goal_consultation_conversation_service.create(session, goal, payload.title)
    return GoalConsultationConversationRead(
        id=entry.id, title=entry.title, created_at=entry.created_at
    )


@router.get(
    "/goals/{goal_id}/consultation/conversations",
    response_model=list[GoalConsultationConversationRead],
)
def list_conversations(
    goal_id: int, session: Session = Depends(get_db)
) -> list[GoalConsultationConversationRead]:
    """この目標の会話一覧を作成日時の古い順で返す（S11、開発Todo v1.2 W7）。"""
    goal = goal_service.get_goal(session, goal_id)
    entries = goal_consultation_conversation_service.list_for_goal(session, goal)
    return [
        GoalConsultationConversationRead(
            id=entry.id, title=entry.title, created_at=entry.created_at
        )
        for entry in entries
    ]


@router.delete(
    "/goals/{goal_id}/consultation/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    goal_id: int, conversation_id: int, session: Session = Depends(get_db)
) -> None:
    """会話を削除する（所属する相談履歴も連鎖削除される、S11、開発Todo v1.2 W7）。"""
    goal = goal_service.get_goal(session, goal_id)
    goal_consultation_conversation_service.delete(session, goal, conversation_id)
    session.commit()


@router.get("/goals/{goal_id}/consultation/limits", response_model=GoalConsultationLimitsRead)
def get_limits(goal_id: int, session: Session = Depends(get_db)) -> GoalConsultationLimitsRead:
    """質問の上限文字数を返す（入力欄の文字数表示と事前チェックに使う）。

    上限値自体は目標に依存しない設定だが、画面（目標詳細の相談タブ）側の呼び出しを
    他の目標相談APIと同じ`/goals/{goal_id}/...`の形に揃える（goal_idの妥当性検証も兼ねる）。
    """
    goal_service.get_goal(session, goal_id)
    return GoalConsultationLimitsRead(
        max_question_chars=setting_reader.get_int(session, AI_GOAL_CONSULTATION_QUESTION_MAX_CHARS)
    )


@router.get(
    "/goals/{goal_id}/consultation/history", response_model=list[GoalConsultationHistoryItemRead]
)
def list_history(
    goal_id: int, session: Session = Depends(get_db)
) -> list[GoalConsultationHistoryItemRead]:
    """相談履歴の一覧を作成日時の古い順で返す（S10、開発Todo v1.1 V7）。"""
    goal = goal_service.get_goal(session, goal_id)
    entries = goal_consultation_log_service.list_for_goal(session, goal)
    return [
        GoalConsultationHistoryItemRead(
            id=entry.id,
            conversation_id=entry.conversation_id,
            question=entry.question,
            status=entry.answer_status,
            answer=entry.answer_body or None,
            cited_dates=list(entry.cited_dates),
            cited_weeks=[
                GoalConsultationCitedWeek(start=start, end=end) for start, end in entry.cited_weeks
            ],
            created_at=entry.created_at,
        )
        for entry in entries
    ]


@router.delete(
    "/goals/{goal_id}/consultation/history/{log_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_history_item(goal_id: int, log_id: int, session: Session = Depends(get_db)) -> None:
    """相談履歴を1件削除する（S10、開発Todo v1.1 V7）。"""
    goal = goal_service.get_goal(session, goal_id)
    goal_consultation_log_service.delete(session, goal, log_id)
    session.commit()
