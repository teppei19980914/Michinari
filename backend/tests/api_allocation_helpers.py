"""API経由でリソース配分を用意するためのテスト共通処理。

リソース配分がスロット単位の分数になったことで（実装フェーズ分割計画書Phase28〜29）、
資格試験目標を進行中にするには「時間枠の登録」と「その枠への配分」の2手順が必要になった。
比率方式では `PATCH /goals/{id}` に resource_ratio を渡すだけで済んでいた箇所を置き換える。
各テストファイルへ同じ手順を書き写すのを避けるためここへ集約する（CLAUDE.md DRYの原則）。
"""

#: 既定で作る時間枠（全曜日・机上・2時間）。個々のテストが枠の形に依存しない場合に使う。
_DEFAULT_SLOT = {
    "name": "テスト用時間枠",
    "start_time": "20:00:00",
    "end_time": "22:00:00",
    "environment": "PC",
    "weekdays": [0, 1, 2, 3, 4, 5, 6],
}

#: 既定の配分時間（分）。既定枠（120分）に収まり、複数目標を並行させても超過しない量。
DEFAULT_ALLOCATION_MINUTES = 30


def create_slot(client, **overrides) -> dict:
    """時間枠を1件登録する。"""
    payload = {**_DEFAULT_SLOT, **overrides}
    response = client.post("/api/v1/resources/slots", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def ensure_slot(client, **overrides) -> dict:
    """時間枠が1件も無ければ登録し、既にあれば先頭を返す。"""
    existing = client.get("/api/v1/resources/slots").json()
    if existing and not overrides:
        return existing[0]
    return create_slot(client, **overrides)


def allocate(client, goal_id: int, minutes: int = DEFAULT_ALLOCATION_MINUTES) -> dict:
    """全ての時間枠へ同じ分数を配分する（時間枠が無ければ既定の枠を作る）。

    比率方式の `PATCH /goals/{id} {"resource_ratio": x}` に相当する。
    """
    ensure_slot(client)
    slots = client.get("/api/v1/resources/slots").json()
    response = client.put(
        f"/api/v1/goals/{goal_id}/slot-allocations",
        json={"allocations": [{"slot_id": slot["id"], "minutes": minutes} for slot in slots]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def slot_minutes_payload(client, minutes: int) -> list[dict]:
    """日次報告の `slot_minutes` 送信値を組み立てる（時間枠が無ければ既定の枠を作る）。"""
    slot = ensure_slot(client)
    return [{"slot_id": slot["id"], "minutes": minutes}]
