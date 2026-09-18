"""資格試験テンプレートAPIのテスト（実装フェーズ分割計画書Phase38）。"""


def test_get_exam_templates_returns_the_six_bundled_templates(client):
    response = client.get("/api/v1/exam-templates")

    assert response.status_code == 200
    body = response.json()
    ids = {template["id"] for template in body}
    assert ids == {"it_passport", "fe", "ap", "sc", "nw", "db"}


def test_get_exam_templates_includes_subjects_and_materials(client):
    response = client.get("/api/v1/exam-templates")

    fe = next(template for template in response.json() if template["id"] == "fe")
    assert [subject["name"] for subject in fe["subjects"]] == ["科目A", "科目B"]
    assert all(subject["passing_score"] == 60 for subject in fe["subjects"])
    assert len(fe["materials"]) >= 1
