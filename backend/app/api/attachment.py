"""添付ファイルのAPI（開発Todo_添付ファイル機能_v1.0）。

goal非依存の共通プールのため、`/goals/{goal_id}/...`配下ではなく独立した`/attachments`
配下に置く（A8）。登録・一覧・削除・上限取得だけを担う（CODING_RULES.md、API層は
ドメイン例外のHTTP変換のみ）。
"""

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.attachment import AttachmentLimitsRead, AttachmentRead
from app.services import attachment_service

router = APIRouter(tags=["attachment"])


@router.post("/attachments", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile = File(...), session: Session = Depends(get_db)
) -> AttachmentRead:
    """PDFをアップロードし、テキスト抽出して登録する（A2・A3・A4）。"""
    content = await file.read()
    attachment = attachment_service.register(
        session, file_name=file.filename or "", content=content
    )
    session.commit()
    return AttachmentRead(
        id=attachment.id, file_name=attachment.file_name, char_count=attachment.char_count
    )


@router.get("/attachments", response_model=list[AttachmentRead])
def list_attachments(session: Session = Depends(get_db)) -> list[AttachmentRead]:
    """登録順（id昇順）で一覧を返す。"""
    return [
        AttachmentRead(id=entry.id, file_name=entry.file_name, char_count=entry.char_count)
        for entry in attachment_service.list_all(session)
    ]


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment_id: int, session: Session = Depends(get_db)) -> None:
    """添付ファイルを削除する（P3：常に削除を許可する）。"""
    attachment_service.delete(session, attachment_id)
    session.commit()


@router.get("/attachments/limits", response_model=AttachmentLimitsRead)
def get_attachment_limits(session: Session = Depends(get_db)) -> AttachmentLimitsRead:
    """画面が表示・事前チェックに使う上限を返す（A7・A10・P1）。"""
    limits = attachment_service.get_limits(session)
    return AttachmentLimitsRead(
        max_file_chars=limits.max_file_chars,
        max_count=limits.max_count,
        max_upload_size_mb=limits.max_upload_size_mb,
    )
