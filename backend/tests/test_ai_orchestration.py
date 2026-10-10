"""`send_and_log()`が応答言語の指示を追記することの単体テスト（日英i18n対応、2026-10）。

`display.locale`に応じて`AI_LANGUAGE_DIRECTIVE_JA`/`_EN`のどちらを追記するかが
正しく切り替わること、追記後の文面がそのまま送信・ログ記録されることを確かめる。
全AI呼び出しサービスがこの関数を経由するため、ここで固定しておけば各サービス側に
同じテストを重複させる必要がない（CODING_RULES.md①DRYの原則）。
"""

from app.ai import client as ai_client
from app.ai import orchestration as ai_orchestration
from app.ai import rate_limiter
from app.constants.enums import AiPurpose, ConversationScope
from app.models.ai import AiConversation, AiLog
from app.services import settings_service


def _make_conversation(session, *, scope_key="probe"):
    conversation = AiConversation(
        goal_id=None,
        scope=ConversationScope.DAILY_MESSAGE,
        scope_key=scope_key,
        conversation_uid="chat-probe",
        folder_uid=None,
        last_parent_order=0,
    )
    session.add(conversation)
    session.commit()
    return conversation


def _install_fake_send(monkeypatch, captured: list[str]):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)

    def _fake(session, *, chat_uid, message):
        captured.append(message)
        return ai_client.SendResult(response_text="応答", latency_ms=1)

    monkeypatch.setattr(ai_client, "send_message", _fake)


def test_send_and_log_appends_japanese_directive_by_default(seeded_session, monkeypatch):
    conversation = _make_conversation(seeded_session)
    captured: list[str] = []
    _install_fake_send(monkeypatch, captured)

    ai_orchestration.send_and_log(
        seeded_session,
        purpose=AiPurpose.DAILY_MESSAGE,
        conversation=conversation,
        prompt_text="本文",
        prompt_chars=2,
        was_truncated=False,
    )

    assert captured == ["本文\n\n必ず日本語で回答してください。"]


def test_send_and_log_appends_english_directive_when_locale_is_english(
    seeded_session, monkeypatch
):
    settings_service.update_app_settings(seeded_session, display={"locale": "en"})
    conversation = _make_conversation(seeded_session)
    captured: list[str] = []
    _install_fake_send(monkeypatch, captured)

    ai_orchestration.send_and_log(
        seeded_session,
        purpose=AiPurpose.DAILY_MESSAGE,
        conversation=conversation,
        prompt_text="Body",
        prompt_chars=4,
        was_truncated=False,
    )

    assert captured == ["Body\n\nPlease respond in English."]


def test_send_and_log_records_the_directive_in_the_logged_request_body(
    seeded_session, monkeypatch
):
    conversation = _make_conversation(seeded_session)
    _install_fake_send(monkeypatch, [])

    ai_orchestration.send_and_log(
        seeded_session,
        purpose=AiPurpose.DAILY_MESSAGE,
        conversation=conversation,
        prompt_text="本文",
        prompt_chars=2,
        was_truncated=False,
    )

    log = seeded_session.query(AiLog).one()
    assert log.request_body == "本文\n\n必ず日本語で回答してください。"
