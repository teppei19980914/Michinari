"""目標相談チャット（読書目標、S10）のカテゴリ別の変数組み立て（開発Todo v1.1 V5）。

カテゴリ非依存の処理は`goal_consultation_service_common.py`を参照。既存の`build_*`関数を
そのまま再利用し、再実装しない（資格のgoal_consultation_service_exam.pyと同じ方針）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.enums import AiPurpose
from app.models.goal import Goal
from app.services import ai_context_reading
from app.services.goal_consultation_service_common import CategoryContext

#: 本が未登録（READING目標作成直後でBookTabから書籍情報を入力する前）の場合の表示
#: （資格の「対象教材はありません」と同じ考え方）。
_NO_BOOK_TEXT = "（本が登録されていません）"


def build_context(session: Session, goal: Goal, today: dt.date) -> CategoryContext:
    """{{book_summary}}・{{reading_metrics}}と{{recent_logs}}の生ログを組み立てる。

    品質指標の推移・リプラン履歴に相当する概念が読書目標に無いため、代わりに本の情報・
    読書の指標の2項目とする（開発Todo v1.1 V3）。
    """
    book = goal.book
    if book is None:
        fixed_variables = {"book_summary": _NO_BOOK_TEXT, "reading_metrics": _NO_BOOK_TEXT}
        raw_entries = []
    else:
        fixed_variables = {
            "book_summary": ai_context_reading.build_retrospective_book_summary_text(book),
            "reading_metrics": ai_context_reading.build_reading_overall_metrics_text(
                session, book
            ),
        }
        raw_entries = ai_context_reading.build_recent_recalls_entries(
            session, [book], goal.start_date, today
        )
    return CategoryContext(
        purpose=AiPurpose.GOAL_CONSULTATION_READING,
        fixed_variables=fixed_variables,
        raw_entries=raw_entries,
    )
