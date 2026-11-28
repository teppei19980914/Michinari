"""公開API（アップロード・差し替え・公開停止）。APIトークン必須（開発Todo_Web公開_v1.0
単位2、D-19・D-20・D-21）。

ローカルアプリ（単位4）がこれらのエンドポイントを呼ぶ。ブラウザ閲覧・回答API
（`app/api/view.py`・`app/api/quiz_answer.py`）とは別の認証方式（Bearerトークン）のため、
CSRF対策は不要（Cookieのようなambient credentialではなく、呼び出し元が明示的に付与する
ヘッダのため。STRIDE分析5章でCSRF対策が必須なのは「ブラウザ→閲覧・回答API」行のみで、
「ローカル→公開API」行には無い）。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_account_from_api_token, get_db
from app.models.account import PublishAccount
from app.schemas.gantt import GanttSnapshotUploadRequest
from app.schemas.quiz import QuizQuestionUploadRequest
from app.schemas.vocab import VocabDeckUploadRequest
from app.services import publish_service

router = APIRouter(prefix="/publish", tags=["publish"])


@router.put("/gantt/{local_goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def put_gantt(
    local_goal_id: int,
    body: GanttSnapshotUploadRequest,
    account: PublishAccount = Depends(get_account_from_api_token),
    db: Session = Depends(get_db),
) -> None:
    publish_service.upsert_gantt_snapshot(db, account, local_goal_id, body)


@router.delete("/gantt/{local_goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gantt(
    local_goal_id: int,
    account: PublishAccount = Depends(get_account_from_api_token),
    db: Session = Depends(get_db),
) -> None:
    publish_service.delete_gantt_snapshot(db, account, local_goal_id)


@router.put("/vocab/{local_deck_id}", status_code=status.HTTP_204_NO_CONTENT)
def put_vocab(
    local_deck_id: int,
    body: VocabDeckUploadRequest,
    account: PublishAccount = Depends(get_account_from_api_token),
    db: Session = Depends(get_db),
) -> None:
    publish_service.upsert_vocab_deck(db, account, local_deck_id, body)


@router.delete("/vocab/{local_deck_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vocab(
    local_deck_id: int,
    account: PublishAccount = Depends(get_account_from_api_token),
    db: Session = Depends(get_db),
) -> None:
    publish_service.delete_vocab_deck(db, account, local_deck_id)


@router.put("/quiz/{local_deck_id}", status_code=status.HTTP_204_NO_CONTENT)
def put_quiz(
    local_deck_id: int,
    body: QuizQuestionUploadRequest,
    account: PublishAccount = Depends(get_account_from_api_token),
    db: Session = Depends(get_db),
) -> None:
    publish_service.replace_quiz_questions(db, account, local_deck_id, body.questions)


@router.delete("/quiz/{local_deck_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quiz(
    local_deck_id: int,
    account: PublishAccount = Depends(get_account_from_api_token),
    db: Session = Depends(get_db),
) -> None:
    publish_service.delete_quiz_questions(db, account, local_deck_id)
