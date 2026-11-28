"""「今日」の論理日APIの統合テスト（開発Todo_Web公開_v1.0 D-09、単位2）。"""

from datetime import UTC, date, datetime

from tests.publish_helpers import create_and_login


def test_get_today_returns_logical_date_for_logged_in_account(client):
    create_and_login(client, "alice")

    response = client.get("/api/v1/today")

    assert response.status_code == 200
    returned_date = date.fromisoformat(response.json()["logical_date"])
    # 既定の`today_boundary_hour=0`ではUTCの日付そのまま（D-09、ローカルのシステム時刻
    # のタイムゾーンに依存させないため、`date.today()`ではなくUTC基準で比較する）。
    assert returned_date == datetime.now(UTC).date()


def test_get_today_without_session_is_rejected(client):
    response = client.get("/api/v1/today")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REQUIRED"
