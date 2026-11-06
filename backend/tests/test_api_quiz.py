"""復習クイズAPIのテスト（データ構造編5.6、開発Todo_復習クイズ_v1.0）。"""

import datetime as dt

from app.models.quiz import QuizQuestion
from tests.diary_helpers import make_exam_goal
from tests.quiz_helpers import stub_quiz_ai
from tests.recap_helpers import seed_theme

TODAY = dt.date.today()


def _make_question(session, theme, **overrides) -> QuizQuestion:
    defaults = dict(
        theme_id=theme.id,
        question_text="問題文",
        choice_1="A",
        choice_2="B",
        choice_3="C",
        choice_4="D",
        correct_choice_index=1,
        explanation="解説",
        citation_date=dt.date(2026, 3, 9),
        interval_index=0,
        next_due_date=TODAY,
    )
    defaults.update(overrides)
    question = QuizQuestion(**defaults)
    session.add(question)
    session.commit()
    return question


def test_get_today_quiz_returns_due_questions_with_theme_name(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    _make_question(seeded_session, theme)

    response = client.get("/api/v1/quiz/today")

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["theme_name"] == "メール関連"
    assert body[0]["choices"] == ["A", "B", "C", "D"]
    assert "correct_choice_index" not in body[0]
    assert "explanation" not in body[0]


def test_get_today_quiz_excludes_not_yet_due_questions(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    _make_question(seeded_session, theme, next_due_date=TODAY + dt.timedelta(days=5))

    response = client.get("/api/v1/quiz/today")

    assert response.status_code == 200
    assert response.json() == []


def test_answer_quiz_correct_returns_result_and_advances_interval(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    question = _make_question(seeded_session, theme)

    response = client.post(f"/api/v1/quiz/{question.id}/answer", json={"choice_index": 1})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_correct"] is True
    assert body["correct_choice_index"] == 1
    assert body["explanation"] == "解説"
    assert body["citation_date"] == "2026-03-09"
    assert dt.date.fromisoformat(body["next_due_date"]) > TODAY


def test_answer_quiz_incorrect_returns_false(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    question = _make_question(seeded_session, theme)

    response = client.post(f"/api/v1/quiz/{question.id}/answer", json={"choice_index": 0})

    assert response.status_code == 200, response.text
    assert response.json()["is_correct"] is False


def test_answer_quiz_unknown_question_returns_404(client):
    response = client.post("/api/v1/quiz/999999/answer", json={"choice_index": 0})
    assert response.status_code == 404


def test_answer_quiz_invalid_choice_index_is_rejected(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    question = _make_question(seeded_session, theme)

    response = client.post(f"/api/v1/quiz/{question.id}/answer", json={"choice_index": 4})

    assert response.status_code == 400


def test_generate_theme_quiz_creates_questions(seeded_session, client, monkeypatch):
    goal = make_exam_goal(seeded_session)
    theme = seed_theme(seeded_session, goal, "メール関連", "本文", [dt.date(2026, 3, 9)])
    stub_quiz_ai(
        monkeypatch,
        (
            "問題: SMTPの役割は？\n"
            "選択肢1: a\n選択肢2: b\n選択肢3: c\n選択肢4: d\n"
            "正解: 1\n解説: 説明\n出典: 2026-03-09"
        ),
    )

    response = client.post(f"/api/v1/themes/{theme.id}/quiz/generate")

    assert response.status_code == 200, response.text
    assert response.json()["created"] == 1


def test_generate_theme_quiz_unknown_theme_returns_404(client):
    response = client.post("/api/v1/themes/999999/quiz/generate")
    assert response.status_code == 404
