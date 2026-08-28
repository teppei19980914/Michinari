"""システム情報APIのテスト（仕様書6.14 SC-15）。"""


def test_get_system_info_returns_app_version_and_libraries(client):
    response = client.get("/api/v1/system-info")

    assert response.status_code == 200
    body = response.json()
    assert body["app_version"]
    assert body["python_version"]
    assert body["built_at"] is None
    assert any(lib["name"] == "fastapi" for lib in body["backend_libraries"])
    assert any(lib["name"] == "react" for lib in body["frontend_libraries"])
