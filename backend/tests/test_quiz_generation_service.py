"""復習クイズのAI生成のテスト（AI送信はモックで検証する）。"""

import datetime as dt
import time

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


def test_parse_blocks_does_not_hang_on_adversarial_repetition(seeded_session, monkeypatch):
    """セキュリティレビューで確認されたReDoS（CWE-1333）の回帰テスト。

    `選択肢1:`等の区切りリテラルを含む行を大量に繰り返す応答（利用者の報告本文を経由した
    間接プロンプトインジェクション、またはAIの反復出力の故障モードを想定）を渡しても、
    破滅的バックトラッキングで無限に近い時間停止しないことを確認する（1秒以内に完了）。
    改修前のパターン（`.+?`の連鎖＋`re.DOTALL`）ではn=16で3.6秒、増加率からn=40〜50で
    数時間停止すると実測されていた。
    """
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    # `_MAX_BLOCK_CHARS`(2000)の多層防御だけに頼らず、正規表現自体が安全であることを
    # 確認するため、その内側に収まる長さで全フィールドのリテラルを繰り返す（出典行は
    # 置かず、最終的にマッチ全体を失敗させて最後までバックトラッキングを試みさせる）。
    repeat_unit = "選択肢1: x\n選択肢2: x\n選択肢3: x\n選択肢4: x\n正解: 1\n解説: x\n"
    adversarial = "問題: q\n" + repeat_unit * 25
    assert len(adversarial) < 2000
    stub_quiz_ai(monkeypatch, adversarial)

    started = time.monotonic()
    created = quiz_generation_service.generate_for_theme(seeded_session, goal, theme)
    elapsed = time.monotonic() - started

    assert created == 0
    assert elapsed < 1.0


def test_generate_for_theme_keeps_valid_blocks_and_drops_invalid_ones(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    response = _valid_block("2026-03-09") + "\n===\n" + _valid_block("1999-01-01")
    stub_quiz_ai(monkeypatch, response)

    created = quiz_generation_service.generate_for_theme(seeded_session, goal, theme)

    assert created == 1


def test_generate_for_theme_caps_created_count_at_questions_per_theme(seeded_session, monkeypatch):
    """AIが`quiz.questions_per_theme`（既定3）を超える有効な問題を返しても、採用数は
    設定を超えない（開発Todo §5「1テーマからの生成数」の基準）。"""
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    response = "\n===\n".join(_valid_block() for _ in range(5))
    stub_quiz_ai(monkeypatch, response)

    created = quiz_generation_service.generate_for_theme(seeded_session, goal, theme)

    assert created == 3
    assert seeded_session.query(QuizQuestion).count() == 3


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
