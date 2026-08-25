"""データ管理のAPI（仕様書6.12 SC-12、データ構造編6.2、実装フェーズ分割計画書Phase10）。"""

import json

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.data import BackupRead
from app.services import backup_service
from app.services.exceptions import ValidationError

router = APIRouter(prefix="/data", tags=["data"])


def _serialize_backup(info: backup_service.BackupInfo) -> BackupRead:
    return BackupRead(id=info.id, created_at=info.created_at, size_bytes=info.size_bytes)


@router.get("/export")
def export_data() -> JSONResponse:
    """全データのエクスポート（仕様書6.12、実装フェーズ分割計画書Phase10完了条件
    「JSON出力をインポートして復元できる」）。"""
    data = backup_service.export_all_data()
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": 'attachment; filename="michinari_export.json"'},
    )


@router.post("/import", status_code=status.HTTP_204_NO_CONTENT)
async def import_data(file: UploadFile) -> None:
    """データのインポート（仕様書6.12「既存データの上書きを確認」。確認モーダルはフロント側
    (MD-xx) で行い、本APIは確認済みの上書き実行のみを担う）。"""
    raw = await file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("インポートファイルが有効なJSONではありません") from exc
    backup_service.import_all_data(data)


@router.post("/backup", response_model=BackupRead, status_code=status.HTTP_201_CREATED)
def create_backup(session: Session = Depends(get_db)) -> BackupRead:
    info = backup_service.create_backup(session)
    session.commit()
    return _serialize_backup(info)


@router.get("/backups", response_model=list[BackupRead])
def list_backups() -> list[BackupRead]:
    return [_serialize_backup(info) for info in backup_service.list_backups()]


@router.post("/backups/{backup_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_backup(backup_id: str) -> None:
    backup_service.restore_backup(backup_id)
