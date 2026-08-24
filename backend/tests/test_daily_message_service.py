"""daily_message_service のテスト（データ構造編6.2 GET /daily-message、
ロジック・プロンプト編17.4、実装フェーズ分割計画書Phase5完了条件
「今日の一言が同日中に再生成されない」）。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.ai.exceptions import AiError
from app.constants.enums import GoalStatus, QualityMetricType
from app.models.ai import AiConversation
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyMessage
from app.services import daily_message_service


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _cleanup_committed_rows(seeded_session):
    """get_or_generateはAI呼び出し失敗時にcommitする（ai_logのエラー記録を残すため、
    16.8）。後始末パターンはtest_daily_feedback_service.pyと同じ。
    """
    yield
    from app.models.base import Base

    seeded_session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        seeded_session.execute(table.delete())
    seeded_session.commit()


def _make_goal(session, name="目標A"):
    goal = Goal(name=name, start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
    session.add(goal)
    session.flush()
    return goal


def _make_material(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        name="教材A",
        unit_label="ページ",
        total_amount=100.0,
        planned_cycles=1,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 12, 31),
        quality_metric_type=QualityMetricType.NONE,
        display_order=1,
    )
    defaults.update(overrides)
    material = Material(**defaults)
    session.add(material)
    session.flush()
    return material


def _stub_send_message(monkeypatch, *, response="今日も頑張りましょう", raise_exc=None):
    calls = []

    def _fake(session, *, chat_uid, message):
        calls.append({"chat_uid": chat_uid, "message": message})
        if raise_exc is not None:
            raise raise_exc
        return ai_client.SendResult(response_text=response, latency_ms=50)

    monkeypatch.setattr(ai_client, "send_message", _fake)
    monkeypatch.setattr(
        ai_client, "create_chat", lambda session, *, assistant_uid, title: "chat-uid-daily-msg"
    )
    return calls


def test_get_or_generate_raises_when_prompt_template_missing(seeded_session):
    from app.constants.enums import AiPurpose
    from app.models.setting import PromptTemplate
    from app.services.exceptions import ValidationError

    seeded_session.query(PromptTemplate).filter_by(purpose=AiPurpose.DAILY_MESSAGE.value).delete()
    seeded_session.flush()

    with pytest.raises(ValidationError):
        daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))


def test_get_or_generate_creates_on_first_call(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)
    calls = _stub_send_message(monkeypatch)

    result = daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))

    assert result.target_date == dt.date(2026, 8, 24)
    assert result.body == "今日も頑張りましょう"
    assert len(calls) == 1
    assert seeded_session.query(DailyMessage).count() == 1


def test_get_or_generate_does_not_regenerate_same_day(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)
    calls = _stub_send_message(monkeypatch)

    first = daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))
    second = daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))

    assert first.id == second.id
    assert len(calls) == 1  # 2回目はAI呼び出しをしない


def test_get_or_generate_uses_conversation_with_no_folder(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)
    _stub_send_message(monkeypatch)

    daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))

    conversation = seeded_session.query(AiConversation).one()
    assert conversation.goal_id is None
    assert conversation.folder_uid is None
    # last_parent_orderの更新はai/orchestration.send_and_logに共通化されており、
    # 日次報告フィードバックだけでなく今日の一言でも成功時に更新されることを確認する
    # （リファクタ前は日次報告フィードバックにしか実装されていなかった片手落ちの回帰防止）。
    assert conversation.last_parent_order == 1


def test_get_or_generate_raises_when_ai_fails_and_does_not_save_partial_message(
    seeded_session, monkeypatch
):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)
    _stub_send_message(monkeypatch, raise_exc=AiError("通信失敗"))

    with pytest.raises(AiError):
        daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))

    assert seeded_session.query(DailyMessage).count() == 0
