"""ヘルスチェック（`GET /health`、付録A「デプロイ手順」6）。認証不要。"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except OperationalError:
        return {"status": "error", "database": "unreachable"}
    return {"status": "ok", "database": "ok"}
