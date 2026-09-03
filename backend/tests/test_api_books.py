"""書籍・読書目標APIのテスト（データ構造編5.3・6.2、仕様書6.2・6.10・7.1、
実装フェーズ分割計画書Phase15）。

資格試験目標のAPIテスト（test_api_goals.py）と対になる、読書目標（category=READING）の
CRUD・状態遷移・バリデーションのテスト。
"""


def _create_reading_goal(client, name="読書目標A", start_date="2026-01-01"):
    response = client.post(
        "/api/v1/goals",
        json={"category": "READING", "name": name, "start_date": start_date},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_exam_goal(client, name="資格目標A", start_date="2026-01-01"):
    response = client.post("/api/v1/goals", json={"name": name, "start_date": start_date})
    assert response.status_code == 201, response.text
    return response.json()


def _add_book(
    client, goal_id, title="書籍A", total_pages=None, start_date="2026-01-01", due_date="2026-06-30"
):
    payload = {
        "title": title,
        "total_pages": total_pages,
        "start_date": start_date,
        "due_date": due_date,
    }
    response = client.post(f"/api/v1/goals/{goal_id}/book", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _make_activatable_reading_goal(client):
    goal = _create_reading_goal(client)
    _add_book(client, goal["id"])
    return goal


# --- 目標作成のcategory対応 ---


def test_create_goal_defaults_to_exam_category(client):
    goal = _create_exam_goal(client)
    assert goal["category"] == "EXAM"


def test_create_reading_goal(client):
    goal = _create_reading_goal(client)
    assert goal["category"] == "READING"
    assert goal["resource_ratio"] == 0.0

    detail = client.get(f"/api/v1/goals/{goal['id']}").json()
    assert detail["exam_subjects"] == []
    assert detail["materials"] == []
    assert detail["book"] is None


# --- 書籍の作成 ---


def test_create_book_succeeds(client):
    goal = _create_reading_goal(client)

    book = _add_book(client, goal["id"], title="達人プログラマー", total_pages=350)

    assert book["title"] == "達人プログラマー"
    assert book["goal_id"] == goal["id"]
    assert book["total_pages"] == 350
    assert book["current_streak"] == 0
    assert book["last_reading_date"] is None
    assert book["progress_rate"] is None

    detail = client.get(f"/api/v1/goals/{goal['id']}").json()
    assert detail["book"]["title"] == "達人プログラマー"


def test_create_second_book_is_rejected(client):
    goal = _create_reading_goal(client)
    _add_book(client, goal["id"])

    response = client.post(
        f"/api/v1/goals/{goal['id']}/book",
        json={"title": "2冊目", "start_date": "2026-01-01", "due_date": "2026-06-30"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BOOK_ALREADY_EXISTS"


def test_create_book_on_exam_goal_is_rejected(client):
    goal = _create_exam_goal(client)

    response = client.post(
        f"/api/v1/goals/{goal['id']}/book",
        json={"title": "書籍A", "start_date": "2026-01-01", "due_date": "2026-06-30"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_book_rejects_start_date_after_due_date(client):
    goal = _create_reading_goal(client)

    response = client.post(
        f"/api/v1/goals/{goal['id']}/book",
        json={"title": "書籍A", "start_date": "2026-06-30", "due_date": "2026-01-01"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- 書籍の更新 ---


def test_update_book_succeeds(client):
    goal = _create_reading_goal(client)
    book = _add_book(client, goal["id"])

    response = client.patch(
        f"/api/v1/books/{book['id']}", json={"title": "改題後のタイトル", "total_pages": 400}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "改題後のタイトル"
    assert body["total_pages"] == 400


def test_update_book_author_start_date_and_due_date(client):
    goal = _create_reading_goal(client)
    book = _add_book(client, goal["id"])

    response = client.patch(
        f"/api/v1/books/{book['id']}",
        json={"author": "夏目漱石", "start_date": "2026-02-01", "due_date": "2026-07-31"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["author"] == "夏目漱石"
    assert body["start_date"] == "2026-02-01"
    assert body["due_date"] == "2026-07-31"


def test_update_book_rejects_start_date_after_due_date(client):
    goal = _create_reading_goal(client)
    book = _add_book(client, goal["id"], start_date="2026-01-01", due_date="2026-06-30")

    response = client.patch(f"/api/v1/books/{book['id']}", json={"start_date": "2026-12-31"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_missing_book_returns_404(client):
    response = client.patch("/api/v1/books/9999", json={"title": "存在しない"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- 状態遷移 ---


def test_activate_reading_goal_requires_book(client):
    goal = _create_reading_goal(client)

    response = client.post(f"/api/v1/goals/{goal['id']}/activate")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_activate_reading_goal_succeeds(client):
    goal = _make_activatable_reading_goal(client)

    response = client.post(f"/api/v1/goals/{goal['id']}/activate")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACTIVE"


def test_complete_book_closes_goal_with_result(client):
    goal = _make_activatable_reading_goal(client)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    book = client.get(f"/api/v1/goals/{goal['id']}").json()["book"]

    response = client.post(f"/api/v1/books/{book['id']}/complete")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CLOSED_WITH_RESULT"
    assert response.json()["closed_at"] is not None


def test_complete_book_on_draft_goal_is_rejected(client):
    goal = _create_reading_goal(client)
    book = _add_book(client, goal["id"])

    response = client.post(f"/api/v1/books/{book['id']}/complete")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_close_reading_goal_without_completing_book_is_interruption(client):
    """POST /goals/{id}/close は読了ではなく中断に相当する（仕様書7.1）。"""
    goal = _make_activatable_reading_goal(client)
    client.post(f"/api/v1/goals/{goal['id']}/activate")

    response = client.post(f"/api/v1/goals/{goal['id']}/close", json={})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    confirmed = client.post(
        f"/api/v1/goals/{goal['id']}/close", json={"confirm_without_result": True}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CLOSED_WITHOUT_RESULT"


def test_update_book_on_closed_goal_is_rejected(client):
    goal = _make_activatable_reading_goal(client)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    book = client.get(f"/api/v1/goals/{goal['id']}").json()["book"]
    client.post(f"/api/v1/books/{book['id']}/complete")

    response = client.patch(f"/api/v1/books/{book['id']}", json={"title": "更新後"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


# --- リソース配分の対象外（要件定義書R-64） ---


def test_reading_goal_cannot_set_resource_ratio(client):
    goal = _create_reading_goal(client)

    response = client.patch(f"/api/v1/goals/{goal['id']}", json={"resource_ratio": 0.5})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_reading_goal_does_not_count_toward_exam_resource_ratio(client):
    """読書目標はresource_ratioの合計計算に算入されない（要件定義書R-64）。
    資格試験目標がリソース配分100%を使い切っていても、読書目標のactivateはリソース超過に
    ならない（読書はそもそもリソース配分を要求しないため）。
    """
    exam_goal = _create_exam_goal(client)
    client.patch(f"/api/v1/goals/{exam_goal['id']}", json={"resource_ratio": 1.0})
    subject = client.post(
        f"/api/v1/goals/{exam_goal['id']}/subjects",
        json={
            "name": "科目A",
            "exam_date_type": "RANGE",
            "exam_date_from": "2026-06-01",
            "exam_date_to": "2026-06-10",
        },
    ).json()
    client.post(
        f"/api/v1/goals/{exam_goal['id']}/materials",
        json={
            "name": "教材A",
            "unit_label": "ページ",
            "total_amount": 100,
            "planned_cycles": 1,
            "subject_ids": [subject["id"]],
            "start_date": "2026-01-01",
            "due_date_is_manual": False,
        },
    )
    assert client.post(f"/api/v1/goals/{exam_goal['id']}/activate").status_code == 200

    reading_goal = _make_activatable_reading_goal(client)
    response = client.post(f"/api/v1/goals/{reading_goal['id']}/activate")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACTIVE"


def test_reading_goal_pause_then_resume_skips_resource_ratio_validation(client):
    """読書目標は元よりresource_ratio=0のため、一時停止→進行中の復帰時にactivate_goalと
    同じくリソース配分検証を適用しない（mainのアーカイブ機能とのマージで発覚したresume_goal
    の回帰防止。EXAM目標であればresource_ratio<=0はRESOURCE_RATIO_REQUIREDで拒否される）。
    """
    goal = _make_activatable_reading_goal(client)
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    client.post(f"/api/v1/goals/{goal['id']}/pause")

    response = client.post(f"/api/v1/goals/{goal['id']}/resume")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACTIVE"
