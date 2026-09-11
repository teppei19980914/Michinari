"""読書目標（goal / book / reading_log の入力）をテストから組み立てるための共通処理。

書籍の列が増減するたびに各テストファイルの生成コードを同じ内容で直す必要があり、実際に
`book.total_pages` の必須化（実装フェーズ分割計画書Phase32）で12箇所の横並び修正が発生した。
同じ組み立てを書き写すのを避けるためここへ集約する（CLAUDE.md DRYの原則、allocation_helpers
と同じ位置づけ）。

日次記録（daily_record）の作り方はテストごとに事情が異なる（新規作成／既存の再利用／
確定状態の違い）ため、`reading_log` 行そのものの生成は各テストファイルに残している。
本モジュールが引き受けるのは、列の増減の影響を受ける Book と ReadingLogItem の組み立てである。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.enums import GoalCategory, GoalStatus
from app.models.book import Book
from app.models.goal import Goal
from app.services.record_service import ReadingLogItem

#: 書籍の既定値。読了目標日を余裕のある日付にしておき、残日数に依存するテストだけが
#: due_date を明示して上書きする。
_BOOK_DEFAULTS: dict = {
    "title": "書籍A",
    "total_pages": 300,
    "start_date": dt.date(2026, 1, 1),
    "due_date": dt.date(2026, 12, 31),
}


def make_reading_goal(
    session: Session, *, name: str = "読書目標A", status: GoalStatus = GoalStatus.ACTIVE
) -> Goal:
    """読書目標（category=READING）を1件作成する。"""
    goal = Goal(
        category=GoalCategory.READING,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=status,
    )
    session.add(goal)
    session.flush()
    return goal


def make_book(session: Session, goal_id: int, **overrides) -> Book:
    """書籍を1件作成する。列を増やす場合は _BOOK_DEFAULTS だけを直せばよい。"""
    defaults = dict(_BOOK_DEFAULTS, goal_id=goal_id)
    defaults.update(overrides)
    book = Book(**defaults)
    session.add(book)
    session.flush()
    return book


def reading_log_item(book_id: int, **overrides) -> ReadingLogItem:
    """想起記録の登録入力（record_service へ渡す ReadingLogItem）を組み立てる。"""
    defaults = dict(book_id=book_id, recall_body="今日読んだ内容の想起", current_page=10)
    defaults.update(overrides)
    return ReadingLogItem(**defaults)
