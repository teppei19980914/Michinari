"""振り返り（テーマ累積）APIのテスト（仕様書6.1.3、データ構造編5.6）。

テーマと報告の準備はサービス層（recap_service）で直接行い、APIの応答・検証・エラー変換を見る。
"""

import datetime as dt

from app.models.recap import RecapTheme
from app.services import recap_service
from tests.diary_helpers import finalize_diary, make_exam_goal


def _seed_theme(session, goal, name, body, days):
    """指定日の報告を作り、テーマへ分類する。body は本文として直接設定する。"""
    for day in days:
        finalize_diary(session, goal, day, diary_learned=f"{name}の学び{day.day}")
    pending = recap_service.collect_pending_entries(
        session, goal, dt.date(2026, 3, 1), dt.date(2026, 3, 31)
    )
    pending = [e for e in pending if e.classified_at is None]
    recap_service.apply_classification(session, goal, {e.id: [name] for e in pending})
    theme = session.query(RecapTheme).filter_by(goal_id=goal.id, name=name).one()
    theme.body = body
    session.commit()
    return theme


def test_list_returns_themes_with_entry_counts(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    _seed_theme(
        seeded_session, goal, "メール関連", "本文A", [dt.date(2026, 3, 9), dt.date(2026, 3, 10)]
    )
    _seed_theme(seeded_session, goal, "認証", "本文B", [dt.date(2026, 3, 11)])

    response = client.get(f"/api/v1/goals/{goal.id}/recap-themes")

    assert response.status_code == 200, response.text
    body = response.json()
    assert {t["name"]: t["entry_count"] for t in body} == {"メール関連": 2, "認証": 1}


def test_list_unknown_goal_returns_404(client):
    response = client.get("/api/v1/goals/999999/recap-themes")
    assert response.status_code == 404


def test_detail_returns_body_and_entries_in_date_order(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    theme = _seed_theme(
        seeded_session, goal, "メール関連", "本文A", [dt.date(2026, 3, 10), dt.date(2026, 3, 9)]
    )

    response = client.get(f"/api/v1/recap-themes/{theme.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "メール関連"
    assert body["body"] == "本文A"
    assert [e["record_date"] for e in body["entries"]] == ["2026-03-09", "2026-03-10"]
    assert body["entries"][0]["source_kind"] == "DIARY"


def test_detail_unknown_theme_returns_404(client):
    assert client.get("/api/v1/recap-themes/999999").status_code == 404


def test_rename_updates_the_name(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    theme = _seed_theme(seeded_session, goal, "メール", "本文", [dt.date(2026, 3, 9)])

    response = client.patch(f"/api/v1/recap-themes/{theme.id}", json={"name": "メール関連"})

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "メール関連"


def test_rename_to_existing_name_returns_conflict(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    _seed_theme(seeded_session, goal, "メール関連", "A", [dt.date(2026, 3, 9)])
    theme = _seed_theme(seeded_session, goal, "認証", "B", [dt.date(2026, 3, 10)])

    response = client.patch(f"/api/v1/recap-themes/{theme.id}", json={"name": "メール関連"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RECAP_THEME_NAME_CONFLICT"


def test_rename_with_empty_name_is_rejected(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    theme = _seed_theme(seeded_session, goal, "メール", "本文", [dt.date(2026, 3, 9)])

    response = client.patch(f"/api/v1/recap-themes/{theme.id}", json={"name": ""})

    assert response.status_code == 400


def test_merge_moves_entries_and_joins_bodies(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    source = _seed_theme(seeded_session, goal, "メール", "SMTP", [dt.date(2026, 3, 9)])
    target = _seed_theme(seeded_session, goal, "メール関連", "DKIM", [dt.date(2026, 3, 10)])
    source_id = source.id

    response = client.post(
        f"/api/v1/recap-themes/{source_id}/merge", json={"target_theme_id": target.id}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == target.id
    assert body["body"] == "DKIM\n\nSMTP"
    assert [e["record_date"] for e in body["entries"]] == ["2026-03-09", "2026-03-10"]
    assert client.get(f"/api/v1/recap-themes/{source_id}").status_code == 404


def test_merge_does_not_duplicate_shared_entries(seeded_session, client):
    from app.models.recap import RecapEntry, RecapThemeLink

    goal = make_exam_goal(seeded_session)
    source = _seed_theme(seeded_session, goal, "メール", "A", [dt.date(2026, 3, 9)])
    target = _seed_theme(seeded_session, goal, "メール関連", "B", [dt.date(2026, 3, 10)])
    shared = seeded_session.query(RecapEntry).filter_by(record_date=dt.date(2026, 3, 9)).one()
    seeded_session.add(RecapThemeLink(theme_id=target.id, entry_id=shared.id))
    seeded_session.commit()

    response = client.post(
        f"/api/v1/recap-themes/{source.id}/merge", json={"target_theme_id": target.id}
    )

    assert response.status_code == 200, response.text
    assert [e["record_date"] for e in response.json()["entries"]] == ["2026-03-09", "2026-03-10"]


def test_merge_into_same_theme_is_a_no_op(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    theme = _seed_theme(seeded_session, goal, "メール", "本文", [dt.date(2026, 3, 9)])

    response = client.post(
        f"/api/v1/recap-themes/{theme.id}/merge", json={"target_theme_id": theme.id}
    )

    assert response.status_code == 200
    assert response.json()["body"] == "本文"


def test_merge_across_goals_returns_404(seeded_session, client):
    goal = make_exam_goal(seeded_session, name="A")
    other = make_exam_goal(seeded_session, name="B")
    source = _seed_theme(seeded_session, goal, "メール", "A", [dt.date(2026, 3, 9)])
    target = _seed_theme(seeded_session, other, "メール", "B", [dt.date(2026, 3, 10)])

    response = client.post(
        f"/api/v1/recap-themes/{source.id}/merge", json={"target_theme_id": target.id}
    )

    assert response.status_code == 404


def test_merge_into_unknown_theme_returns_404(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    source = _seed_theme(seeded_session, goal, "メール", "A", [dt.date(2026, 3, 9)])

    response = client.post(
        f"/api/v1/recap-themes/{source.id}/merge", json={"target_theme_id": 999999}
    )

    assert response.status_code == 404


def test_merge_keeps_target_body_when_source_body_is_empty(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    source = _seed_theme(seeded_session, goal, "メール", "", [dt.date(2026, 3, 9)])
    target = _seed_theme(seeded_session, goal, "メール関連", "DKIM", [dt.date(2026, 3, 10)])

    response = client.post(
        f"/api/v1/recap-themes/{source.id}/merge", json={"target_theme_id": target.id}
    )

    assert response.status_code == 200, response.text
    assert response.json()["body"] == "DKIM"


def test_merge_takes_source_body_when_target_body_is_empty(seeded_session, client):
    goal = make_exam_goal(seeded_session)
    source = _seed_theme(seeded_session, goal, "メール", "SMTP", [dt.date(2026, 3, 9)])
    target = _seed_theme(seeded_session, goal, "メール関連", "", [dt.date(2026, 3, 10)])

    response = client.post(
        f"/api/v1/recap-themes/{source.id}/merge", json={"target_theme_id": target.id}
    )

    assert response.status_code == 200, response.text
    assert response.json()["body"] == "SMTP"
