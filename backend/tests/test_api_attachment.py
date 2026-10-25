"""添付ファイルのAPI層テスト（開発Todo_添付ファイル機能_v1.0）。"""

from tests.pdf_helpers import build_minimal_pdf, build_pdf_without_text

_SAMPLE_TEXT = "document content, long enough to pass the minimum length check in tests"


def test_upload_attachment_returns_created_entry(client):
    response = client.post(
        "/api/v1/attachments",
        files={"file": ("exam.pdf", build_minimal_pdf(_SAMPLE_TEXT), "application/pdf")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["file_name"] == "exam.pdf"
    assert body["char_count"] == len(_SAMPLE_TEXT)
    assert "id" in body


def test_upload_attachment_rejects_pdf_without_extractable_text(client):
    response = client.post(
        "/api/v1/attachments",
        files={"file": ("image.pdf", build_pdf_without_text(), "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_attachments_returns_registered_entries(client):
    client.post(
        "/api/v1/attachments",
        files={"file": ("a.pdf", build_minimal_pdf(_SAMPLE_TEXT), "application/pdf")},
    )

    response = client.get("/api/v1/attachments")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["file_name"] == "a.pdf"


def test_delete_attachment_removes_entry(client):
    created = client.post(
        "/api/v1/attachments",
        files={"file": ("a.pdf", build_minimal_pdf(_SAMPLE_TEXT), "application/pdf")},
    ).json()

    response = client.delete(f"/api/v1/attachments/{created['id']}")

    assert response.status_code == 204
    assert client.get("/api/v1/attachments").json() == []


def test_delete_attachment_returns_not_found_for_missing_id(client):
    response = client.delete("/api/v1/attachments/999")

    assert response.status_code == 404


def test_get_attachment_limits_returns_seeded_defaults(client):
    response = client.get("/api/v1/attachments/limits")

    assert response.status_code == 200
    body = response.json()
    assert body["max_file_chars"] == 20000
    assert body["max_count"] == 50
    assert body["max_upload_size_mb"] == 20
