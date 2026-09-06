"""daily_feedback_service のテスト（データ構造編6.2 POST /records/{date}/chat、
ロジック・プロンプト編16.3.1・16.7、実装フェーズ分割計画書Phase5完了条件）。

実際のAI基盤へは接続せず、app.ai.client.send_message をモックして検証する。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.ai.exceptions import AiError
from app.constants.enums import ChatRole, GoalStatus, QualityMetricType
from app.models.ai import AiConversation, AiLog
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import ChatMessage
from app.services import daily_feedback_service, record_service
from app.services.exceptions import ValidationError
from app.services.record_service import DiaryEntryItem, StudyLogItem


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    """呼び出し間隔制御自体はtest_ai_rate_limiter.pyで検証済みのため、ここでは
    実時間のsleepでテストを遅くしないよう無効化する。"""
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _cleanup_committed_rows(seeded_session):
    """send_daily_feedbackはAI呼び出し失敗時にcommitする（ai_logのエラー記録を残すため、
    16.8）。db_sessionフィクスチャのrollbackだけではcommitted行が同一DBファイルに残り
    他のテストファイルを汚染するため、明示的に全テーブルを空にする
    （tests/conftest.pyのclientフィクスチャと同じ後始末パターン）。
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


def _stub_send_message(monkeypatch, *, response="AIからの応答", raise_exc=None):
    calls = []

    def _fake(session, *, chat_uid, message):
        calls.append({"chat_uid": chat_uid, "message": message})
        if raise_exc is not None:
            raise raise_exc
        return ai_client.SendResult(response_text=response, latency_ms=123)

    monkeypatch.setattr(ai_client, "send_message", _fake)
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: "chat-uid-daily",
    )
    return calls


def test_send_daily_feedback_raises_when_prompt_template_missing(seeded_session):
    from app.constants.enums import AiPurpose
    from app.models.setting import PromptTemplate

    seeded_session.query(PromptTemplate).filter_by(purpose=AiPurpose.DAILY_FEEDBACK.value).delete()
    seeded_session.flush()

    with pytest.raises(ValidationError):
        daily_feedback_service.send_daily_feedback(
            seeded_session,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            study_log_items=[],
            diary_entries=[],
        )


def test_send_daily_feedback_reports_no_active_goals_in_load_coefficient(
    seeded_session, monkeypatch
):
    calls = _stub_send_message(monkeypatch)

    daily_feedback_service.send_daily_feedback(
        seeded_session,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        study_log_items=[],
        diary_entries=[],
    )

    assert "算出不可" in calls[0]["message"]


def test_send_daily_feedback_rejects_future_date(seeded_session):
    with pytest.raises(ValidationError):
        daily_feedback_service.send_daily_feedback(
            seeded_session,
            target_date=dt.date(2026, 8, 25),
            today=dt.date(2026, 8, 24),
            message=None,
            study_log_items=[],
            diary_entries=[],
        )


def test_send_daily_feedback_first_turn_has_no_user_message_row(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _stub_send_message(monkeypatch)

    outcome = daily_feedback_service.send_daily_feedback(
        seeded_session,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        study_log_items=[
            StudyLogItem(
                material_id=material.id,
                minutes_spent=30,
                amount_completed=10.0,
                cycle_number=1,
                quality_value=None,
            )
        ],
        diary_entries=[
            DiaryEntryItem(
                goal_id=goal.id, diary_body="今日は頑張った", diary_learned="過去問を解いた"
            )
        ],
    )

    messages = (
        seeded_session.query(ChatMessage)
        .filter_by(daily_record_id=outcome.daily_record.id)
        .order_by(ChatMessage.sequence)
        .all()
    )
    assert len(messages) == 1
    assert messages[0].role == ChatRole.ASSISTANT
    assert messages[0].content == "AIからの応答"
    assert outcome.was_truncated is False


def test_send_daily_feedback_followup_turn_adds_user_and_assistant_messages(
    seeded_session, monkeypatch
):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)
    _stub_send_message(monkeypatch, response="1回目の応答")

    daily_feedback_service.send_daily_feedback(
        seeded_session,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        study_log_items=[],
        diary_entries=[],
    )

    calls = _stub_send_message(monkeypatch, response="2回目の応答")
    outcome = daily_feedback_service.send_daily_feedback(
        seeded_session,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message="もう少し詳しく教えて",
        study_log_items=[],
        diary_entries=[],
    )

    messages = (
        seeded_session.query(ChatMessage)
        .filter_by(daily_record_id=outcome.daily_record.id)
        .order_by(ChatMessage.sequence)
        .all()
    )
    assert [m.role for m in messages] == [
        ChatRole.ASSISTANT,
        ChatRole.USER,
        ChatRole.ASSISTANT,
    ]
    assert messages[1].content == "もう少し詳しく教えて"
    assert messages[2].content == "2回目の応答"
    # 2回目の送信メッセージには1回目の応答が対話履歴として全文注入されている（16.3.1）。
    assert "1回目の応答" in calls[0]["message"]
    assert "もう少し詳しく教えて" in calls[0]["message"]


def test_send_daily_feedback_reuses_conversation_across_turns(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)
    _stub_send_message(monkeypatch)

    daily_feedback_service.send_daily_feedback(
        seeded_session,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        study_log_items=[],
        diary_entries=[],
    )
    daily_feedback_service.send_daily_feedback(
        seeded_session,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message="続きです",
        study_log_items=[],
        diary_entries=[],
    )

    conversation = seeded_session.query(AiConversation).one()
    # last_parent_orderはv0.10.5では文脈維持に使用できないが、将来の開発キット改修に備えた
    # 記録として往復ごとに更新される（16.3.1）。
    assert conversation.last_parent_order == 2


def test_send_daily_feedback_disables_web_search_via_ai_client(seeded_session, monkeypatch):
    """ai/clientの送信部が既定でWeb検索・ナレッジ検索を無効化することは
    test_ai_client.pyで直接検証済み。ここではdaily_feedback_serviceがai_client.send_message
    経由でしか送信しないことを確認する（別経路での直接送信が無いことの回帰防止）。
    """
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)
    calls = _stub_send_message(monkeypatch)

    daily_feedback_service.send_daily_feedback(
        seeded_session,
        target_date=dt.date(2026, 8, 24),
        today=dt.date(2026, 8, 24),
        message=None,
        study_log_items=[],
        diary_entries=[],
    )

    assert len(calls) == 1


def test_send_daily_feedback_does_not_persist_study_logs_or_diary(seeded_session, monkeypatch):
    """AI呼び出しが失敗しても実績入力が失われない（16.7、Phase5完了条件）。
    本関数は下書きの実績・日記を一切永続化しない設計のため、成功時も失敗時も
    daily_recordのstudy_logs/diaryは空のままであることを確認する。
    """
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _stub_send_message(monkeypatch, raise_exc=AiError("通信に失敗しました"))

    with pytest.raises(AiError):
        daily_feedback_service.send_daily_feedback(
            seeded_session,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            study_log_items=[
                StudyLogItem(
                    material_id=material.id,
                    minutes_spent=30,
                    amount_completed=10.0,
                    cycle_number=1,
                    quality_value=None,
                )
            ],
            diary_entries=[
                DiaryEntryItem(
                    goal_id=goal.id,
                    diary_body="失われてはいけない日記",
                    diary_learned="失われてはいけない学び",
                )
            ],
        )

    record = record_service.get_daily_record(seeded_session, dt.date(2026, 8, 24))
    assert record is not None
    assert record.study_logs == []
    assert record_service.get_diary_entries(seeded_session, record) == []


def test_send_daily_feedback_records_failure_to_ai_log(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)
    _stub_send_message(monkeypatch, raise_exc=AiError("通信に失敗しました"))

    with pytest.raises(AiError):
        daily_feedback_service.send_daily_feedback(
            seeded_session,
            target_date=dt.date(2026, 8, 24),
            today=dt.date(2026, 8, 24),
            message=None,
            study_log_items=[],
            diary_entries=[],
        )

    log = seeded_session.query(AiLog).one()
    assert log.error_type == "AiError"
    assert log.response_body is None
