"""振り返りのAI呼び出しを差し替えるテスト用ヘルパー（分類と本文更新の応答を振り分ける）。"""

import re

from app.ai import client as ai_client
from app.ai import rate_limiter


def _stub_ai(monkeypatch, *, classify, body):
    """classify(message)・body(message) が応答文字列を返す。プロンプトの種類で振り分ける。"""
    calls = []

    def _fake(session, *, chat_uid, message):
        calls.append(message)
        if "既存のテーマ（" in message:
            return ai_client.SendResult(response_text=classify(message), latency_ms=1)
        return ai_client.SendResult(response_text=body(message), latency_ms=1)

    monkeypatch.setattr(ai_client, "send_message", _fake)
    counter = iter(range(1000))
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: f"chat-{next(counter)}",
    )
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)
    return calls


def _all_ids_to(theme_names):
    def _classify(message):
        ids = re.findall(r"#(\d+)（", message)
        return "\n".join(f"#{i}: {theme_names}" for i in ids)

    return _classify
