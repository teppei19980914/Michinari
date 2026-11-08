"""復習クイズの出題選択・解答記録・テーマ変更時の削除（開発Todo_復習クイズ_v1.0）。

AI呼び出しは含まない（`quiz_generation_service`が担う）。間隔の算出（正解で次の間隔へ、
不正解で最初の間隔へ）・出題対象の選定（`next_due_date <= 今日`、資格試験・読書の
進行中の目標のみ）はいずれもDB読み取りと単純な配列参照のみで行う。
"""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants.app_setting_keys import QUIZ_DAILY_LIMIT, QUIZ_INTERVAL_DAYS
from app.constants.enums import GoalCategory, GoalStatus
from app.models.base import utcnow
from app.models.goal import Goal
from app.models.quiz import QuizAnswerLog, QuizQuestion
from app.models.recap import RecapTheme
from app.services import setting_reader
from app.services.exceptions import NotFoundError

#: 出題対象の目標種別（テーマ累積・仕様書6.1.3と同じ、仕事は対象外）。
_ELIGIBLE_CATEGORIES = (GoalCategory.EXAM, GoalCategory.READING)


def get_question(session: Session, question_id: int) -> QuizQuestion:
    question = session.get(QuizQuestion, question_id)
    if question is None:
        raise NotFoundError("quiz_question", question_id)
    return question


def get_due_questions(session: Session, today: dt.date) -> list[QuizQuestion]:
    """今日出題すべきクイズを、1日の上限（`quiz.daily_limit`）まで返す。

    紐づく目標が進行中（ACTIVE）かつ資格試験・読書のもののみ対象とする
    （`recap_generation_service.run_all`が参照する`list_active_exam_goals`／
    `list_active_reading_goals`と同じ絞り込み、CLAUDE.md DRYの原則）。
    """
    limit = setting_reader.get_int(session, QUIZ_DAILY_LIMIT)
    return list(
        session.scalars(
            select(QuizQuestion)
            .join(RecapTheme, RecapTheme.id == QuizQuestion.theme_id)
            .join(Goal, Goal.id == RecapTheme.goal_id)
            .where(
                QuizQuestion.next_due_date <= today,
                Goal.status == GoalStatus.ACTIVE,
                Goal.category.in_(_ELIGIBLE_CATEGORIES),
            )
            .order_by(QuizQuestion.next_due_date, QuizQuestion.id)
            .limit(limit)
        ).all()
    )


def count_questions_for_theme(session: Session, theme_id: int) -> int:
    """テーマが持つクイズの件数（0＝未生成。テーマ詳細の「作る」／「作り直す」表示分け用）。"""
    return count_questions_by_theme(session, [theme_id]).get(theme_id, 0)


def count_questions_by_theme(session: Session, theme_ids: list[int]) -> dict[int, int]:
    """複数テーマのクイズ件数を1回の問い合わせで返す（テーマ一覧表示用、N+1禁止）。"""
    if not theme_ids:
        return {}
    rows = session.execute(
        select(QuizQuestion.theme_id, func.count(QuizQuestion.id))
        .where(QuizQuestion.theme_id.in_(theme_ids))
        .group_by(QuizQuestion.theme_id)
    ).all()
    return dict(rows)


def record_answer(session: Session, question: QuizQuestion, is_correct: bool) -> QuizQuestion:
    """解答を記録し、間隔を進める（正解）か最初の間隔へ戻す（不正解）。

    `quiz_answer_log`へ1行追加する（分析用、テーマが変更されても削除しない）。
    """
    intervals = setting_reader.get_int_list(session, QUIZ_INTERVAL_DAYS)
    now = utcnow()
    if is_correct and intervals:
        question.interval_index = min(question.interval_index + 1, len(intervals) - 1)
    else:
        question.interval_index = 0
    days = intervals[question.interval_index] if intervals else 1
    question.next_due_date = now.date() + dt.timedelta(days=days)
    question.last_answered_at = now
    session.add(
        QuizAnswerLog(
            theme_id=question.theme_id,
            question_id=question.id,
            is_correct=is_correct,
            answered_at=now,
        )
    )
    session.flush()
    return question


def delete_questions_for_theme(
    session: Session, theme_id: int, *, only_unanswered: bool
) -> None:
    """テーマに紐づく`quiz_question`を削除する（`quiz_answer_log`は削除しない）。

    `only_unanswered=True`（利用者操作「作り直す」）は未出題（`last_answered_at`が
    NULL）の行のみを削除し、解答済み（進行中）の行は残す。`only_unanswered=False`
    （テーマの改名・統合・再構築、目標のアーカイブ・削除）は全行を削除する
    （開発Todo §0 U3）。
    """
    stmt = select(QuizQuestion).where(QuizQuestion.theme_id == theme_id)
    if only_unanswered:
        stmt = stmt.where(QuizQuestion.last_answered_at.is_(None))
    for question in session.scalars(stmt).all():
        session.delete(question)
    session.flush()
