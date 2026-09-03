"""daily_message_service のテスト（データ構造編5.5・6.2 GET /daily-message、
ロジック・プロンプト編17.4、実装フェーズ分割計画書Phase5完了条件
「今日の一言が同日中に再生成されない」、未決事項L-04「目標ごとの独立生成」）。
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
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: f"chat-uid-{len(calls)}",
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

    assert len(result) == 1
    assert result[0].target_date == dt.date(2026, 8, 24)
    assert result[0].goal_id == goal.id
    assert result[0].body == "今日も頑張りましょう"
    assert len(calls) == 1
    assert seeded_session.query(DailyMessage).count() == 1


def test_get_or_generate_does_not_regenerate_same_day(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)
    calls = _stub_send_message(monkeypatch)

    first = daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))
    second = daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))

    assert first[0].id == second[0].id
    assert len(calls) == 1  # 2回目はAI呼び出しをしない


def test_get_or_generate_scopes_conversation_to_goal(seeded_session, monkeypatch):
    """未決事項L-04: 会話は目標ごとにスコープされ、goal_idがNULLにならないこと
    （weekly_summary_serviceと同じ goal=goal パターン）。"""
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)
    _stub_send_message(monkeypatch)

    daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))

    conversation = seeded_session.query(AiConversation).one()
    assert conversation.goal_id == goal.id
    assert conversation.folder_uid is None
    assert conversation.last_parent_order == 1


def test_get_or_generate_zero_active_goals_is_goal_independent(seeded_session, monkeypatch):
    """ACTIVEな目標が1件も無い日は、従来通りgoal_id=NULLの1件のみ生成すること。"""
    _stub_send_message(monkeypatch)

    result = daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))

    assert len(result) == 1
    assert result[0].goal_id is None
    conversation = seeded_session.query(AiConversation).one()
    assert conversation.goal_id is None


def test_get_or_generate_zero_active_goals_does_not_regenerate_same_day(
    seeded_session, monkeypatch
):
    calls = _stub_send_message(monkeypatch)

    first = daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))
    second = daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))

    assert first[0].id == second[0].id
    assert len(calls) == 1


def test_get_or_generate_creates_independent_message_per_goal_without_cross_contamination(
    seeded_session, monkeypatch
):
    """ユーザーの懸念に直接対応する回帰テスト: 目標Aの生成呼び出しに目標Bの情報が
    混入しないこと（逆も同様）。良い方の目標に引っ張られた楽観的な一言が生成される
    リスクを構造的に排除する（未決事項L-04）。
    """
    goal_a = _make_goal(seeded_session, name="目標A")
    goal_b = _make_goal(seeded_session, name="目標B")
    _make_material(seeded_session, goal_a, name="教材Aのみ")
    _make_material(seeded_session, goal_b, name="教材Bのみ")
    calls = _stub_send_message(monkeypatch)

    result = daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))

    assert len(result) == 2
    assert {message.goal_id for message in result} == {goal_a.id, goal_b.id}
    assert len(calls) == 2

    call_by_goal_name = {}
    for call in calls:
        if "教材Aのみ" in call["message"]:
            call_by_goal_name["目標A"] = call["message"]
        elif "教材Bのみ" in call["message"]:
            call_by_goal_name["目標B"] = call["message"]

    assert "教材Bのみ" not in call_by_goal_name["目標A"]
    assert "教材Aのみ" not in call_by_goal_name["目標B"]
    assert "目標A" not in call_by_goal_name["目標B"]
    assert "目標B" not in call_by_goal_name["目標A"]


def test_get_or_generate_only_generates_for_newly_active_goal(seeded_session, monkeypatch):
    """日中に新たにACTIVEになった目標があった場合、既存の目標のメッセージは
    再生成せず、新規目標の分だけ追加生成すること。"""
    goal_a = _make_goal(seeded_session, name="目標A")
    _make_material(seeded_session, goal_a)
    calls = _stub_send_message(monkeypatch, response="目標Aの一言")

    first = daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))
    assert len(first) == 1
    assert len(calls) == 1

    goal_b = _make_goal(seeded_session, name="目標B")
    _make_material(seeded_session, goal_b)
    calls2 = _stub_send_message(monkeypatch, response="目標Bの一言")

    second = daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))

    assert len(second) == 2
    assert len(calls2) == 1  # 目標Aは再生成されない
    by_goal = {message.goal_id: message for message in second}
    assert by_goal[goal_a.id].body == "目標Aの一言"  # 既存のまま
    assert by_goal[goal_b.id].body == "目標Bの一言"  # 新規生成分


def test_get_or_generate_raises_when_ai_fails_and_does_not_save_partial_message(
    seeded_session, monkeypatch
):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)
    _stub_send_message(monkeypatch, raise_exc=AiError("通信失敗"))

    with pytest.raises(AiError):
        daily_message_service.get_or_generate(seeded_session, dt.date(2026, 8, 24))

    assert seeded_session.query(DailyMessage).count() == 0
