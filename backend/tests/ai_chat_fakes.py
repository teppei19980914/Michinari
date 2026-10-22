"""使い捨てチャット方式（質問ごとにチャットを作成→送信→削除→一覧で削除確認）を使う
AI機能のテスト共通フェイク（ヘルプAIアシスタント・目標相談チャット、S10で3カテゴリ分の
テストファイルへ複製が増えたため抽出、CLAUDE.md DRYの原則）。

`app.ai.client`の通信関数を差し替え、送信内容を記録し、用意した応答を返す。
"""

from app.ai import client as ai_client


class FakeAi:
    """`responses`は呼び出しごとに順に使う（残りがなければ最後の応答を繰り返す）。"""

    def __init__(self, monkeypatch, responses: tuple[str, ...]):
        self.responses = list(responses)
        self.sent: list[str] = []
        self.created: list[str] = []
        self.deleted: list[str] = []
        self.listed_after_delete = False
        self._counter = 0
        monkeypatch.setattr(ai_client, "is_authenticated", lambda session: True)
        monkeypatch.setattr(ai_client, "create_chat_in_folder_by_name", self._create)
        monkeypatch.setattr(ai_client, "send_message", self._send)
        monkeypatch.setattr(ai_client, "delete_chat", self._delete)
        monkeypatch.setattr(ai_client, "chat_listed_in_folder", self._listed)

    def _create(self, session, *, assistant_uid, folder_name, title):
        self._counter += 1
        chat_uid = f"chat-{self._counter}"
        self.created.append(chat_uid)
        return chat_uid

    def _send(self, session, *, chat_uid, message):
        self.sent.append(message)
        response = self.responses[min(len(self.sent), len(self.responses)) - 1]
        return ai_client.SendResult(response_text=response, latency_ms=1)

    def _delete(self, session, *, chat_uid):
        self.deleted.append(chat_uid)

    def _listed(self, session, *, folder_name, chat_uid):
        return self.listed_after_delete
