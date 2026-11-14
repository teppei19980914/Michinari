"""復習クイズの出題選択・解答記録・テーマ変更時の削除のテスト（AI非依存）。"""

import datetime as dt

import pytest
from sqlalchemy import select

from app.constants.app_setting_keys import QUIZ_DAILY_LIMIT, QUIZ_INTERVAL_DAYS
from app.constants.enums import GoalCategory, GoalStatus
from app.models.goal import Goal
from app.models.quiz import QuizAnswerLog, QuizQuestion
from app.models.recap import RecapTheme
from app.models.setting import AppSetting
from app.services import quiz_service
from app.services.exceptions import NotFoundError
from tests.diary_helpers import make_exam_goal

TODAY = dt.date(2026, 3, 20)


def _set_setting(session, key, value):
    row = session.scalar(select(AppSetting).where(AppSetting.key == key))
    row.value = value
    session.flush()


def _make_theme(session, goal) -> RecapTheme:
    theme = RecapTheme(goal_id=goal.id, name="テーマ", body="本文")
    session.add(theme)
    session.flush()
    return theme


def _make_question(
    session, theme, *, next_due_date, interval_index=0, last_answered_at=None
) -> QuizQuestion:
    question = QuizQuestion(
        theme_id=theme.id,
        question_text="問題文",
        choice_1="A",
        choice_2="B",
        choice_3="C",
        choice_4="D",
        correct_choice_index=1,
        explanation="解説",
        citation_date=dt.date(2026, 3, 9),
        interval_index=interval_index,
        next_due_date=next_due_date,
        last_answered_at=last_answered_at,
    )
    session.add(question)
    session.flush()
    return question


def test_get_due_questions_returns_only_questions_due_today_or_earlier(seeded_session):
    goal = make_exam_goal(seeded_session)
    theme = _make_theme(seeded_session, goal)
    due = _make_question(seeded_session, theme, next_due_date=TODAY)
    _make_question(seeded_session, theme, next_due_date=TODAY + dt.timedelta(days=1))

    result = quiz_service.get_due_questions(seeded_session, TODAY)

    assert [q.id for q in result] == [due.id]


def test_get_due_questions_excludes_non_active_goals(seeded_session):
    goal = make_exam_goal(seeded_session, status=GoalStatus.PAUSED)
    theme = _make_theme(seeded_session, goal)
    _make_question(seeded_session, theme, next_due_date=TODAY)

    assert quiz_service.get_due_questions(seeded_session, TODAY) == []


def test_get_due_questions_excludes_work_goals(seeded_session):
    goal = Goal(name="仕事", category=GoalCategory.WORK, start_date=TODAY, status=GoalStatus.ACTIVE)
    seeded_session.add(goal)
    seeded_session.flush()
    theme = _make_theme(seeded_session, goal)
    _make_question(seeded_session, theme, next_due_date=TODAY)

    assert quiz_service.get_due_questions(seeded_session, TODAY) == []


def test_get_due_questions_respects_daily_limit(seeded_session):
    goal = make_exam_goal(seeded_session)
    theme = _make_theme(seeded_session, goal)
    for _ in range(3):
        _make_question(seeded_session, theme, next_due_date=TODAY)
    _set_setting(seeded_session, QUIZ_DAILY_LIMIT, "2")

    assert len(quiz_service.get_due_questions(seeded_session, TODAY)) == 2


def test_record_answer_correct_advances_interval_and_logs(seeded_session):
    goal = make_exam_goal(seeded_session)
    theme = _make_theme(seeded_session, goal)
    question = _make_question(seeded_session, theme, next_due_date=TODAY, interval_index=0)
    _set_setting(seeded_session, QUIZ_INTERVAL_DAYS, "1,3,7")

    quiz_service.record_answer(seeded_session, question, True)

    assert question.interval_index == 1
    assert question.next_due_date == question.last_answered_at.date() + dt.timedelta(days=3)
    assert question.last_answered_at is not None
    log = seeded_session.scalar(
        select(QuizAnswerLog).where(QuizAnswerLog.question_id == question.id)
    )
    assert log.is_correct is True
    assert log.theme_id == theme.id


def test_record_answer_correct_at_last_interval_stays_there(seeded_session):
    goal = make_exam_goal(seeded_session)
    theme = _make_theme(seeded_session, goal)
    question = _make_question(seeded_session, theme, next_due_date=TODAY, interval_index=2)
    _set_setting(seeded_session, QUIZ_INTERVAL_DAYS, "1,3,7")

    quiz_service.record_answer(seeded_session, question, True)

    assert question.interval_index == 2


def test_record_answer_incorrect_resets_to_first_interval(seeded_session):
    goal = make_exam_goal(seeded_session)
    theme = _make_theme(seeded_session, goal)
    question = _make_question(seeded_session, theme, next_due_date=TODAY, interval_index=2)
    _set_setting(seeded_session, QUIZ_INTERVAL_DAYS, "1,3,7")

    quiz_service.record_answer(seeded_session, question, False)

    assert question.interval_index == 0
    assert question.next_due_date == question.last_answered_at.date() + dt.timedelta(days=1)
    log = seeded_session.scalar(
        select(QuizAnswerLog).where(QuizAnswerLog.question_id == question.id)
    )
    assert log.is_correct is False


def test_delete_questions_for_theme_only_unanswered_keeps_answered(seeded_session):
    goal = make_exam_goal(seeded_session)
    theme = _make_theme(seeded_session, goal)
    unanswered = _make_question(seeded_session, theme, next_due_date=TODAY)
    answered = _make_question(
        seeded_session, theme, next_due_date=TODAY, last_answered_at=dt.datetime(2026, 3, 1)
    )

    quiz_service.delete_questions_for_theme(seeded_session, theme.id, only_unanswered=True)

    remaining = seeded_session.scalars(select(QuizQuestion)).all()
    assert [q.id for q in remaining] == [answered.id]
    assert seeded_session.get(QuizQuestion, unanswered.id) is None


def test_delete_questions_for_theme_all_deletes_everything_but_keeps_answer_log(seeded_session):
    goal = make_exam_goal(seeded_session)
    theme = _make_theme(seeded_session, goal)
    question = _make_question(
        seeded_session, theme, next_due_date=TODAY, last_answered_at=dt.datetime(2026, 3, 1)
    )
    quiz_service.record_answer(seeded_session, question, True)
    question_id = question.id

    quiz_service.delete_questions_for_theme(seeded_session, theme.id, only_unanswered=False)

    assert seeded_session.scalars(select(QuizQuestion)).all() == []
    log = seeded_session.scalar(select(QuizAnswerLog))
    assert log is not None
    assert log.theme_id == theme.id
    assert log.question_id is None  # SET NULL
    assert question_id is not None


def test_count_questions_by_theme_batches_multiple_themes(seeded_session):
    goal = make_exam_goal(seeded_session)
    theme_a = _make_theme(seeded_session, goal)
    theme_b = RecapTheme(goal_id=goal.id, name="テーマB", body="")
    seeded_session.add(theme_b)
    seeded_session.flush()
    _make_question(seeded_session, theme_a, next_due_date=TODAY)
    _make_question(seeded_session, theme_a, next_due_date=TODAY)

    counts = quiz_service.count_questions_by_theme(seeded_session, [theme_a.id, theme_b.id])

    assert counts == {theme_a.id: 2}
    assert quiz_service.count_questions_for_theme(seeded_session, theme_b.id) == 0


def test_count_questions_by_theme_with_empty_list_returns_empty_dict(seeded_session):
    assert quiz_service.count_questions_by_theme(seeded_session, []) == {}


def test_get_question_raises_not_found_for_unknown_id(seeded_session):
    with pytest.raises(NotFoundError):
        quiz_service.get_question(seeded_session, 999999)
