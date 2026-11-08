"""復習クイズのAI呼び出しを差し替えるテスト用ヘルパー（recap_helpers.pyの_stub_aiと同方式）。"""

from app.ai import client as ai_client
from app.ai import rate_limiter


def stub_quiz_ai(
    monkeypatch, response_text: str | None = None, *, responses: list[str] | None = None
):
    """`response_text`（1回だけ）または`responses`（チャンクごとに順に返す）のいずれかを指定する。"""
    calls: list[str] = []
    queue = list(responses) if responses is not None else None

    def _fake(session, *, chat_uid, message):
        calls.append(message)
        if queue is not None:
            text = queue.pop(0) if queue else ""
        else:
            text = response_text or ""
        return ai_client.SendResult(response_text=text, latency_ms=1)

    monkeypatch.setattr(ai_client, "send_message", _fake)
    counter = iter(range(1000))
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: f"chat-{next(counter)}",
    )
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)
    return calls
