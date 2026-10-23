"""目標相談チャットの質疑サービスのテスト（仕事目標、S10、開発Todo v1.1 V5・V11）。

カテゴリ非依存の検証は資格目標側（test_goal_consultation_service_exam.py）で網羅済みの
ため、ここでは仕事目標固有の変数組み立て（{{work_summary}}・{{work_progress}}・
{{member_summary}}、案件が未登録の場合のフォールバック）と、WORK目標でも質疑が成立する
ことだけを検証する（CODING_RULES.md DRYの原則）。
"""

import datetime as dt

import pytest

from app.ai import rate_limiter
from app.constants.enums import GoalCategory, GoalConsultationAnswerStatus, GoalStatus
from app.models.goal import Goal, GoalConsultationLog
from app.models.record import WorkLog
from app.models.work import WorkAssignment, WorkMember
from app.services import goal_consultation_service_common as service
from tests.ai_chat_fakes import FakeAi
from tests.ai_context_helpers import make_daily_record

_TODAY = dt.date(2026, 1, 20)
_WORK_LOG_DATE = dt.date(2026, 1, 15)

_DEFAULT_RESPONSE = (
    "## 記録から言えること\n順調に進んでいます。\n"
    "## 一般的な助言\n継続しましょう。\n"
    f"[記録: {_WORK_LOG_DATE.isoformat()}]"
)


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _make_work_goal(session, name="仕事目標A"):
    goal = Goal(
        category=GoalCategory.WORK,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_work_assignment(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id, expected_content="想定業務内容", start_date=dt.date(2026, 1, 1)
    )
    defaults.update(overrides)
    work_assignment = WorkAssignment(**defaults)
    session.add(work_assignment)
    session.flush()
    return work_assignment


def _make_work_goal_with_log(session):
    goal = _make_work_goal(session)
    work_assignment = _make_work_assignment(session, goal)
    record = make_daily_record(session, _WORK_LOG_DATE)
    session.add(
        WorkLog(
            daily_record_id=record.id, work_assignment_id=work_assignment.id, body="案件Aを進めた。"
        )
    )
    session.commit()
    return goal, work_assignment


def test_ask_answers_work_goal_with_work_context(seeded_session, monkeypatch):
    goal, _ = _make_work_goal_with_log(seeded_session)
    fake = FakeAi(monkeypatch, (_DEFAULT_RESPONSE,))

    answer = service.ask(
        seeded_session, goal=goal, today=_TODAY, raw_question="今月の成果を上司向けに3行で"
    )

    assert answer.status is GoalConsultationAnswerStatus.ANSWERED
    assert answer.cited_dates == (_WORK_LOG_DATE,)
    prompt = fake.sent[0]
    assert "# 案件の概要" in prompt
    assert "# 進み具合" in prompt
    assert "# チームメンバー" in prompt
    assert "（対象メンバーはいません）" in prompt
    # 資格目標専用の見出しは出ない。
    assert "リプラン履歴" not in prompt


def test_ask_includes_member_characteristics_in_prompt(seeded_session, monkeypatch):
    """チームメンバーの情報（氏名・特徴）を相談の入力に含める（利用者確認済み、V11）。"""
    goal, work_assignment = _make_work_goal_with_log(seeded_session)
    seeded_session.add(
        WorkMember(
            work_assignment_id=work_assignment.id,
            name="山田太郎",
            characteristics="新人で丁寧なフォローが必要",
            consent_confirmed_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        )
    )
    seeded_session.commit()
    fake = FakeAi(monkeypatch, (_DEFAULT_RESPONSE,))

    service.ask(seeded_session, goal=goal, today=_TODAY, raw_question="最近の課題の傾向は？")

    prompt = fake.sent[0]
    assert "山田太郎" in prompt
    assert "新人で丁寧なフォローが必要" in prompt


def test_ask_uses_fallback_text_when_work_assignment_is_not_registered(seeded_session, monkeypatch):
    """WorkAssignmentTabで案件情報を入力する前（WORK目標作成直後）でも質疑は成立する。"""
    goal = _make_work_goal(seeded_session)
    FakeAi(monkeypatch, ("## 記録から言えること\n記録からはまだ判断できません。\n"
                         "## 一般的な助言\n基礎から整理しましょう。\n[根拠: なし]",))

    answer = service.ask(
        seeded_session, goal=goal, today=_TODAY, raw_question="最近の課題の傾向は？"
    )

    assert answer.status is GoalConsultationAnswerStatus.ANSWERED


def test_ask_saves_log_entry_with_work_goal(seeded_session, monkeypatch):
    goal, _ = _make_work_goal_with_log(seeded_session)
    FakeAi(monkeypatch, (_DEFAULT_RESPONSE,))

    service.ask(seeded_session, goal=goal, today=_TODAY, raw_question="今月の成果を上司向けに3行で")

    log = seeded_session.query(GoalConsultationLog).filter_by(goal_id=goal.id).one()
    assert log.answer_status is GoalConsultationAnswerStatus.ANSWERED
