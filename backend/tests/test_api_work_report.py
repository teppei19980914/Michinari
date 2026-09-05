"""月次報告・半期評価APIのテスト（データ構造編6.2、実装フェーズ分割計画書Phase22完了条件）。

総括レポートAPIのテスト（test_api_closure.py）と対になる、仕事目標（category=WORK）の
月次報告・半期評価のCRUDのテスト。
"""

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _create_work_goal_with_assignment(client, name="仕事目標A", start_date="2026-01-01"):
    goal = client.post(
        "/api/v1/goals", json={"category": "WORK", "name": name, "start_date": start_date}
    ).json()
    client.post(
        f"/api/v1/goals/{goal['id']}/work-assignment",
        json={"expected_content": "想定業務内容", "start_date": start_date},
    )
    client.post(f"/api/v1/goals/{goal['id']}/activate")
    return goal


def _stub_send_message(monkeypatch, *, response):
    monkeypatch.setattr(
        ai_client,
        "send_message",
        lambda session, *, chat_uid, message: ai_client.SendResult(
            response_text=response, latency_ms=5
        ),
    )
    counter = iter(range(1000))
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: f"chat-{next(counter)}",
    )


_MONTHLY_RESPONSE = """## 業務内容の要約
API開発を中心に取り組んだ。

## 達成度
3

## 達成状況の振り返り
概ね計画通り進捗した。

## 来月の目標
新機能の実装に着手する。

## 報告・連絡事項
特になし
"""

_SEMIANNUAL_RESPONSE = """## 業務内容の要約
半期を通じてAPI開発を継続した。

## 達成度
2

## 達成状況の振り返り
当初計画を上回るペースで進んだ。

## 次半期の目標
新機能の設計を開始する。
"""


# --- 月次報告 ---


def test_get_monthly_report_returns_null_when_not_generated(client):
    goal = _create_work_goal_with_assignment(client)

    response = client.get(
        f"/api/v1/goals/{goal['id']}/monthly-report", params={"period": "2026-08"}
    )

    assert response.status_code == 200
    assert response.json() is None


def test_generate_monthly_report_creates_and_persists(client, monkeypatch):
    goal = _create_work_goal_with_assignment(client)
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)

    response = client.post(f"/api/v1/goals/{goal['id']}/monthly-report", json={"period": "2026-08"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period_type"] == "MONTHLY"
    assert body["period_key"] == "2026-08"
    assert body["achievement_score"] == 3
    assert body["next_goal_text"] == "新機能の実装に着手する。"
    assert body["edited_at"] is None

    fetched = client.get(
        f"/api/v1/goals/{goal['id']}/monthly-report", params={"period": "2026-08"}
    ).json()
    assert fetched["id"] == body["id"]


def test_generate_monthly_report_without_period_defaults_to_previous_month(client, monkeypatch):
    goal = _create_work_goal_with_assignment(client)
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)

    response = client.post(f"/api/v1/goals/{goal['id']}/monthly-report", json={})

    assert response.status_code == 200, response.text
    # 既定値は前月なので、当月分をperiodなしで取得すると同じ行が返る。
    fetched = client.get(f"/api/v1/goals/{goal['id']}/monthly-report").json()
    assert fetched["id"] == response.json()["id"]


def test_regenerate_monthly_report_overwrites_same_row(client, monkeypatch):
    goal = _create_work_goal_with_assignment(client)
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)
    first = client.post(
        f"/api/v1/goals/{goal['id']}/monthly-report", json={"period": "2026-08"}
    ).json()

    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE.replace("3\n", "1\n"))
    second = client.post(
        f"/api/v1/goals/{goal['id']}/monthly-report", json={"period": "2026-08"}
    ).json()

    assert first["id"] == second["id"]
    assert second["achievement_score"] == 1


def test_generate_monthly_report_on_exam_goal_is_rejected(client, monkeypatch):
    goal = client.post(
        "/api/v1/goals", json={"name": "資格目標A", "start_date": "2026-01-01"}
    ).json()
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)

    response = client.post(f"/api/v1/goals/{goal['id']}/monthly-report", json={})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_generate_anonymized_monthly_report_is_separate_from_original(client, monkeypatch):
    goal = _create_work_goal_with_assignment(client)
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)
    client.post(f"/api/v1/goals/{goal['id']}/monthly-report", json={"period": "2026-08"})

    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE.replace("3\n", "5\n"))
    anon_response = client.post(
        f"/api/v1/goals/{goal['id']}/monthly-report",
        json={"period": "2026-08", "anonymize": True},
    )

    assert anon_response.status_code == 200
    assert anon_response.json()["is_anonymized"] is True
    assert anon_response.json()["achievement_score"] == 5

    original = client.get(
        f"/api/v1/goals/{goal['id']}/monthly-report", params={"period": "2026-08"}
    ).json()
    assert original["achievement_score"] == 3


def test_patch_monthly_report_updates_fields_and_rebuilds_body(client, monkeypatch):
    goal = _create_work_goal_with_assignment(client)
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)
    client.post(f"/api/v1/goals/{goal['id']}/monthly-report", json={"period": "2026-08"})

    response = client.patch(
        f"/api/v1/goals/{goal['id']}/monthly-report",
        params={"period": "2026-08"},
        json={"achievement_score": 5, "next_goal_text": "修正後の来月の目標"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["achievement_score"] == 5
    assert body["next_goal_text"] == "修正後の来月の目標"
    assert body["edited_at"] is not None
    assert "修正後の来月の目標" in body["body"]


def test_patch_monthly_report_creates_row_when_missing(client):
    """前期の記録が無い初回利用者向けの手動シード（要件定義書R-83）。"""
    goal = _create_work_goal_with_assignment(client)

    response = client.patch(
        f"/api/v1/goals/{goal['id']}/monthly-report",
        params={"period": "2026-08"},
        json={"target_goal_text": "手動で設定した目標"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["target_goal_text"] == "手動で設定した目標"


def test_patch_monthly_report_rejects_achievement_score_out_of_range(client, monkeypatch):
    goal = _create_work_goal_with_assignment(client)
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)
    client.post(f"/api/v1/goals/{goal['id']}/monthly-report", json={"period": "2026-08"})

    response = client.patch(
        f"/api/v1/goals/{goal['id']}/monthly-report",
        params={"period": "2026-08"},
        json={"achievement_score": 6},
    )

    assert response.status_code == 400


# --- 半期評価 ---


def test_get_semiannual_review_returns_null_when_not_generated(client):
    goal = _create_work_goal_with_assignment(client)

    response = client.get(
        f"/api/v1/goals/{goal['id']}/semiannual-review", params={"period": "2026-H1"}
    )

    assert response.status_code == 200
    assert response.json() is None


def test_generate_semiannual_review_creates_and_persists(client, monkeypatch):
    goal = _create_work_goal_with_assignment(client)
    _stub_send_message(monkeypatch, response=_SEMIANNUAL_RESPONSE)

    response = client.post(
        f"/api/v1/goals/{goal['id']}/semiannual-review", json={"period": "2026-H1"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period_type"] == "SEMI_ANNUAL"
    assert body["period_key"] == "2026-H1"
    assert body["achievement_score"] == 2
    assert body["report_notes"] is None

    fetched = client.get(
        f"/api/v1/goals/{goal['id']}/semiannual-review", params={"period": "2026-H1"}
    ).json()
    assert fetched["id"] == body["id"]


def test_patch_semiannual_review_updates_fields(client, monkeypatch):
    goal = _create_work_goal_with_assignment(client)
    _stub_send_message(monkeypatch, response=_SEMIANNUAL_RESPONSE)
    client.post(f"/api/v1/goals/{goal['id']}/semiannual-review", json={"period": "2026-H1"})

    response = client.patch(
        f"/api/v1/goals/{goal['id']}/semiannual-review",
        params={"period": "2026-H1"},
        json={"achievement_score": 1},
    )

    assert response.status_code == 200, response.text
    assert response.json()["achievement_score"] == 1


# --- 既存の総括レポートエンドポイントの恒久拒否（データ構造編6.2） ---


def test_generic_retrospective_endpoint_rejects_work_goal(client, monkeypatch):
    goal = _create_work_goal_with_assignment(client)
    _stub_send_message(monkeypatch, response="総括レポート本文")

    response = client.post(f"/api/v1/goals/{goal['id']}/retrospective", json={})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
