"""資格試験テンプレート読込サービスのテスト（実装フェーズ分割計画書Phase38）。"""

from pathlib import Path

from app.services import exam_template_service


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_list_exam_templates_returns_all_bundled_templates() -> None:
    """同梱済みの6試験テンプレートが読み込めること（配布パッケージ対応込みの既定パス）。"""
    templates = exam_template_service.list_exam_templates()

    ids = {template.id for template in templates}
    assert ids == {"it_passport", "fe", "ap", "sc", "nw", "db"}


def test_list_exam_templates_parses_subjects_and_materials(tmp_path: Path) -> None:
    _write(
        tmp_path / "sample.json",
        """
        {
          "id": "sample",
          "exam_name": "サンプル試験",
          "subjects": [
            {"name": "科目A", "passing_score_type": "PERCENTAGE", "passing_score": 60}
          ],
          "materials": [
            {
              "name": "教科書",
              "unit_label": "ページ",
              "total_amount": 100,
              "planned_cycles": 1,
              "subject_names": ["科目A"]
            }
          ]
        }
        """,
    )

    templates = exam_template_service.list_exam_templates(tmp_path)

    assert len(templates) == 1
    assert templates[0].exam_name == "サンプル試験"
    assert templates[0].materials[0].subject_names == ["科目A"]


def test_list_exam_templates_returns_empty_list_when_directory_is_missing(tmp_path: Path) -> None:
    missing_dir = tmp_path / "does-not-exist"

    assert exam_template_service.list_exam_templates(missing_dir) == []


def test_list_exam_templates_skips_a_file_with_invalid_json_syntax(tmp_path: Path) -> None:
    """構文エラーのJSONは、そのファイルのみ読み飛ばし一覧全体を失敗させない。"""
    _write(tmp_path / "broken.json", "{ this is not valid json")

    assert exam_template_service.list_exam_templates(tmp_path) == []


def test_list_exam_templates_skips_a_file_that_fails_schema_validation(tmp_path: Path) -> None:
    """科目が1件も無いなどスキーマ不一致のテンプレートも読み飛ばす。"""
    _write(
        tmp_path / "invalid_schema.json",
        '{"id": "broken", "exam_name": "不備のある試験", "subjects": [], "materials": []}',
    )

    assert exam_template_service.list_exam_templates(tmp_path) == []


def test_list_exam_templates_keeps_valid_files_alongside_an_invalid_one(tmp_path: Path) -> None:
    """1件の不備が、他の正常なテンプレートの読込を妨げないこと。"""
    _write(tmp_path / "a_broken.json", "not json at all")
    _write(
        tmp_path / "b_valid.json",
        """
        {
          "id": "valid",
          "exam_name": "有効な試験",
          "subjects": [
            {"name": "科目A", "passing_score_type": "PERCENTAGE", "passing_score": 60}
          ],
          "materials": []
        }
        """,
    )

    templates = exam_template_service.list_exam_templates(tmp_path)

    assert [template.id for template in templates] == ["valid"]
