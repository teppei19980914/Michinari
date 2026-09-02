"""書籍のAPI（データ構造編6.2、実装フェーズ分割計画書Phase15）。

serialize_book は goals.py（目標詳細への書籍ネスト表示）からも共通処理として使う
（CLAUDE.md DRYの原則、api/materials.pyのserialize_materialと同じ位置づけ）。
書籍の新規作成は目標配下のネストパス（POST /goals/{id}/book）であるため api/goals.py に置く。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.book import Book
from app.schemas.book import BookRead, BookUpdate
from app.schemas.goal import GoalRead
from app.services import book_service, goal_service

router = APIRouter(tags=["books"])


def serialize_book(session: Session, book: Book) -> BookRead:
    """派生値（残日数・直近記録日・連続記録日数・ページ進捗）を都度算出して付与する
    （CLAUDE.md 保存禁止、ロジック・プロンプト編21.2）。"""
    today = goal_service.resolve_today(session)
    progress = book_service.get_book_progress(session, book, today)
    return BookRead(
        id=book.id,
        goal_id=book.goal_id,
        title=book.title,
        author=book.author,
        total_pages=book.total_pages,
        start_date=book.start_date,
        due_date=book.due_date,
        remaining_days=progress.remaining_days,
        last_reading_date=progress.last_reading_date,
        current_streak=progress.current_streak,
        current_page=progress.current_page,
        progress_rate=progress.progress_rate,
    )


@router.patch("/books/{book_id}", response_model=BookRead)
def update_book(book_id: int, payload: BookUpdate, session: Session = Depends(get_db)) -> BookRead:
    book = book_service.get_book(session, book_id)
    book_service.update_book(session, book, **payload.model_dump(exclude_unset=True))
    session.commit()
    return serialize_book(session, book)


@router.post("/books/{book_id}/complete", response_model=GoalRead)
def complete_book(book_id: int, session: Session = Depends(get_db)) -> GoalRead:
    book = book_service.get_book(session, book_id)
    goal = book_service.complete_book(session, book)
    session.commit()
    return GoalRead.model_validate(goal)
