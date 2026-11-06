"""復習クイズのAI生成のテスト（AI送信はモックで検証する）。"""

import datetime as dt

import pytest
from sqlalchemy import select

from app.constants.app_setting_keys import AI_MAX_PROMPT_CHARS
from app.models.quiz import QuizQuestion
from app.models.recap import RecapTheme
from app.models.setting import AppSetting
from app.services import quiz_generation_service, quiz_service
from app.services.exceptions import RecapPromptTooLongError
from tests.diary_helpers import make_exam_goal
from tests.quiz_helpers import stub_quiz_ai
from tests.recap_helpers import seed_theme

TODAY = dt.date(2026, 3, 20)


def _set_setting(session, key, value):
    row = session.scalar(select(AppSetting).where(AppSetting.key == key))
    row.value = value
    session.flush()


def _valid_block(citation: str = "2026-03-09") -> str:
    return (
        "問題: SMTPの役割は？\n"
        "選択肢1: 間違い1\n"
        "選択肢2: 正解\n"
        "選択肢3: 間違い2\n"
        "選択肢4: 間違い3\n"
        "正解: 2\n"
        "解説: SMTPはメール送信の役割を持つ\n"
        f"出典: {citation}"
    )


def test_generate_for_theme_saves_valid_question(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    stub_quiz_ai(monkeypatch, _valid_block())

    created = quiz_generation_service.generate_for_theme(seeded_session, goal, theme)

    assert created == 1
    question = seeded_session.scalar(select(QuizQuestion).where(QuizQuestion.theme_id == theme.id))
    assert question.question_text == "SMTPの役割は？"
    assert question.choice_2 == "正解"
    assert question.correct_choice_index == 1
    assert question.citation_date == dt.date(2026, 3, 9)
    assert question.next_due_date == dt.date.today()
    assert question.interval_index == 0


def test_generate_for_theme_discards_block_with_invalid_citation_date(
    seeded_session, monkeypatch
):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    # 2026-03-10はこのチャンクに実際には含まれていない日付（偽の出典）。
    stub_quiz_ai(monkeypatch, _valid_block("2026-03-10"))

    created = quiz_generation_service.generate_for_theme(seeded_session, goal, theme)

    assert created == 0
    assert seeded_session.scalars(select(QuizQuestion)).all() == []


def test_generate_for_theme_discards_malformed_block(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    stub_quiz_ai(monkeypatch, "形式に合わない応答")

    created = quiz_generation_service.generate_for_theme(seeded_session, goal, theme)

    assert created == 0


def test_generate_for_theme_keeps_valid_blocks_and_drops_invalid_ones(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    response = _valid_block("2026-03-09") + "\n===\n" + _valid_block("1999-01-01")
    stub_quiz_ai(monkeypatch, response)

    created = quiz_generation_service.generate_for_theme(seeded_session, goal, theme)

    assert created == 1


def test_generate_for_theme_without_entries_does_nothing(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    theme = RecapTheme(goal_id=goal.id, name="空のテーマ", body="")
    seeded_session.add(theme)
    seeded_session.flush()
    calls = stub_quiz_ai(monkeypatch, _valid_block())

    created = quiz_generation_service.generate_for_theme(seeded_session, goal, theme)

    assert created == 0
    assert calls == []


def test_regenerate_for_theme_deletes_unanswered_then_regenerates(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    stub_quiz_ai(monkeypatch, _valid_block())
    quiz_generation_service.generate_for_theme(seeded_session, goal, theme)
    seeded_session.commit()
    old_question = seeded_session.scalar(select(QuizQuestion))
    old_question.last_answered_at = dt.datetime(2026, 3, 15)  # 作り直す前に解答済みにしておく
    seeded_session.commit()

    stub_quiz_ai(monkeypatch, _valid_block())
    created = quiz_generation_service.regenerate_for_theme(seeded_session, goal, theme)

    assert created == 1
    # 解答済みだった行は削除対象外（only_unanswered=True）のため、解答済み1件＋新規1件で2件。
    remaining = seeded_session.scalars(select(QuizQuestion)).all()
    assert len(remaining) == 2
    assert sum(1 for q in remaining if q.last_answered_at is None) == 1


def test_run_all_generates_only_for_themes_without_quiz(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    theme_a = seed_theme(seeded_session, goal, "テーマA", "本文A", [dt.date(2026, 3, 9)])
    theme_b = seed_theme(seeded_session, goal, "テーマB", "本文B", [dt.date(2026, 3, 10)])
    stub_quiz_ai(monkeypatch, _valid_block())
    quiz_generation_service.generate_for_theme(seeded_session, goal, theme_a)
    seeded_session.commit()
    calls = stub_quiz_ai(monkeypatch, _valid_block("2026-03-10"))

    total = quiz_generation_service.run_all(seeded_session)

    assert total == 1
    assert len(calls) == 1
    assert quiz_service.count_questions_for_theme(seeded_session, theme_a.id) == 1
    assert quiz_service.count_questions_for_theme(seeded_session, theme_b.id) == 1


def test_prompt_exceeding_limit_is_not_sent(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    _set_setting(seeded_session, AI_MAX_PROMPT_CHARS, "10")
    calls = stub_quiz_ai(monkeypatch, _valid_block())

    with pytest.raises(RecapPromptTooLongError):
        quiz_generation_service.generate_for_theme(seeded_session, goal, theme)

    assert calls == []


def test_run_all_one_goal_failure_does_not_stop_others(seeded_session, monkeypatch):
    goal_ok = make_exam_goal(seeded_session, name="OK")
    goal_fail = make_exam_goal(seeded_session, name="FAIL")
    seed_theme(seeded_session, goal_ok, "テーマOK", "本文", [dt.date(2026, 3, 9)])
    seed_theme(seeded_session, goal_fail, "テーマNG", "本文", [dt.date(2026, 3, 10)])

    real_send = quiz_generation_service._send

    def _boom(session, goal, theme, variables, *, scope_key):
        if goal.id == goal_fail.id:
            raise RuntimeError("boom")
        return real_send(session, goal, theme, variables, scope_key=scope_key)

    stub_quiz_ai(monkeypatch, _valid_block())
    monkeypatch.setattr(quiz_generation_service, "_send", _boom)

    total = quiz_generation_service.run_all(seeded_session)

    assert total == 1
