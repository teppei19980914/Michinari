"""目標相談チャットの質疑サービスのテスト（読書目標、S10、開発Todo v1.1 V5）。

カテゴリ非依存の検証（直列化・禁止語・送信失敗時の後始末等）は資格目標側
（test_goal_consultation_service_exam.py）で網羅済みのため、ここでは読書目標固有の
変数組み立て（{{book_summary}}・{{reading_metrics}}、本が未登録の場合のフォールバック）
と、READING目標でも質疑が成立することだけを検証する（CODING_RULES.md DRYの原則）。
"""

import datetime as dt

import pytest

from app.ai import rate_limiter
from app.constants.enums import GoalConsultationAnswerStatus
from app.models.goal import GoalConsultationLog
from app.models.record import ReadingLog
from app.services import goal_consultation_conversation_service
from app.services import goal_consultation_service_common as service
from tests import reading_helpers
from tests.ai_chat_fakes import FakeAi
from tests.ai_context_helpers import make_daily_record

_TODAY = dt.date(2026, 1, 20)
_RECALL_DATE = dt.date(2026, 1, 15)

_DEFAULT_RESPONSE = (
    "## 記録から言えること\n順調に読み進めています。\n"
    "## 一般的な助言\n継続しましょう。\n"
    f"[記録: {_RECALL_DATE.isoformat()}]"
)


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _make_reading_goal_with_book_and_log(session):
    goal = reading_helpers.make_reading_goal(session)
    book = reading_helpers.make_book(session, goal.id)
    record = make_daily_record(session, _RECALL_DATE)
    session.add(
        ReadingLog(daily_record_id=record.id, book_id=book.id, recall_body="第3章を読んだ。")
    )
    session.commit()
    return goal


def _make_conversation(session, goal):
    """会話継続（S11）のテストで使う会話を1件作る（開発Todo v1.2 W6）。"""
    return goal_consultation_conversation_service.create(session, goal, "").id


def test_ask_answers_reading_goal_with_book_context(seeded_session, monkeypatch):
    goal = _make_reading_goal_with_book_and_log(seeded_session)
    fake = FakeAi(monkeypatch, (_DEFAULT_RESPONSE,))

    conversation_id = _make_conversation(seeded_session, goal)
    answer = service.ask(
        seeded_session,
        goal=goal,
        today=_TODAY,
        conversation_id=conversation_id,
        raw_question="前に読んだ本とのつながりは？",
    )

    assert answer.status is GoalConsultationAnswerStatus.ANSWERED
    assert answer.cited_dates == (_RECALL_DATE,)
    prompt = fake.sent[0]
    assert "# 本の情報" in prompt
    assert "# 読書の指標" in prompt
    assert "書籍A" in prompt  # reading_helpers._BOOK_DEFAULTS["title"]
    # 資格目標専用の見出しは出ない（カテゴリ別テンプレートが正しく選択されている確認）。
    assert "教材の状態" not in prompt
    assert "品質指標の推移" not in prompt


def test_ask_uses_fallback_text_when_book_is_not_registered(seeded_session, monkeypatch):
    """BookTabで書籍情報を入力する前（READING目標作成直後）でも質疑は成立する。"""
    goal = reading_helpers.make_reading_goal(seeded_session)
    fake = FakeAi(monkeypatch, ("## 記録から言えること\n記録からはまだ判断できません。\n"
                                "## 一般的な助言\n基礎から整理しましょう。\n[根拠: なし]",))

    conversation_id = _make_conversation(seeded_session, goal)
    answer = service.ask(
        seeded_session,
        goal=goal,
        today=_TODAY,
        conversation_id=conversation_id,
        raw_question="この本で学んだことを3行で",
    )

    assert answer.status is GoalConsultationAnswerStatus.ANSWERED
    prompt = fake.sent[0]
    assert "（本が登録されていません）" in prompt


def test_ask_saves_log_entry_with_reading_goal(seeded_session, monkeypatch):
    goal = _make_reading_goal_with_book_and_log(seeded_session)
    FakeAi(monkeypatch, (_DEFAULT_RESPONSE,))

    conversation_id = _make_conversation(seeded_session, goal)
    service.ask(
        seeded_session,
        goal=goal,
        today=_TODAY,
        conversation_id=conversation_id,
        raw_question="前に読んだ本とのつながりは？",
    )

    log = seeded_session.query(GoalConsultationLog).filter_by(goal_id=goal.id).one()
    assert log.answer_status is GoalConsultationAnswerStatus.ANSWERED
