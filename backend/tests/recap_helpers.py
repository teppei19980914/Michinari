"""振り返りのAI呼び出しを差し替えるテスト用ヘルパー（分類と本文更新の応答を振り分ける）。"""

import datetime as dt
import re

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.models.recap import RecapTheme
from app.services import recap_service
from tests.diary_helpers import finalize_diary


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


def seed_theme(session, goal, name: str, body: str, days: list[dt.date]) -> RecapTheme:
    """指定日の日記を作り、テーマへ分類する（本文は直接設定）。復習クイズのテスト等で
    「分類済みの報告を持つテーマ」を用意するために使う（test_api_recap.pyの
    `_seed_theme`と同じ処理をテストモジュール間で共有、CLAUDE.md DRYの原則）。
    """
    for day in days:
        finalize_diary(session, goal, day, diary_learned=f"{name}の学び{day.day}")
    pending = recap_service.collect_pending_entries(
        session, goal, dt.date(2026, 1, 1), dt.date(2026, 12, 31)
    )
    pending = [e for e in pending if e.classified_at is None]
    recap_service.apply_classification(session, goal, {e.id: [name] for e in pending})
    theme = session.query(RecapTheme).filter_by(goal_id=goal.id, name=name).one()
    theme.body = body
    session.commit()
    return theme
