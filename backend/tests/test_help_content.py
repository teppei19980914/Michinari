"""ヘルプ本文の生成物（Phase43、開発Todo U8・B-07・B-08）のテスト。

本文の正は `frontend/src/locales/ja.json` の help 名前空間。
生成物 `app/content/help_content.json` が
ja.json と一致すること（書き出し忘れの検出）と、読み込みの形式を確かめる。
"""

import importlib.util
import json
from pathlib import Path

from app.services.help_content import HELP_CONTENT_PATH, load_sections

BACKEND_ROOT = Path(__file__).resolve().parents[1]
JA_JSON_PATH = BACKEND_ROOT.parent / "frontend" / "src" / "locales" / "ja.json"


def _load_export_module():
    spec = importlib.util.spec_from_file_location(
        "export_help_content", BACKEND_ROOT / "scripts" / "export_help_content.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_help_content_matches_ja_json():
    """ja.json を変更したのに生成し直していない場合に失敗する（ドリフトの検出）。"""
    export = _load_export_module()
    ja = json.loads(JA_JSON_PATH.read_text(encoding="utf-8"))

    expected = export.render(export.build_help_content(ja))

    assert HELP_CONTENT_PATH.read_text(encoding="utf-8") == expected


def test_export_is_deterministic():
    export = _load_export_module()
    ja = json.loads(JA_JSON_PATH.read_text(encoding="utf-8"))

    assert export.render(export.build_help_content(ja)) == export.render(
        export.build_help_content(ja)
    )


def test_loaded_sections_have_unique_ids_titles_and_bodies():
    sections = load_sections()

    ids = [section.id for section in sections]
    assert len(ids) == len(set(ids))
    assert all(section.title for section in sections)
    assert all(section.body for section in sections)


def test_section_bodies_keep_only_text_in_definition_order():
    """見出し（title）は本文に含めない。本文は ja.json の定義順の文字列だけ。"""
    export = _load_export_module()
    ja = json.loads(JA_JSON_PATH.read_text(encoding="utf-8"))
    intro = ja["help"]["sections"]["intro"]

    content = export.build_help_content(ja)
    intro_entry = next(section for section in content["sections"] if section["id"] == "intro")

    assert intro_entry["title"] == intro["title"]
    assert intro_entry["body"] == [intro["p1"], intro["p2"], intro["p3"]]


def test_nested_purpose_texts_are_included_in_prompt_variables_section():
    export = _load_export_module()
    ja = json.loads(JA_JSON_PATH.read_text(encoding="utf-8"))

    content = export.build_help_content(ja)
    section = next(s for s in content["sections"] if s["id"] == "promptVariables")

    assert (
        ja["help"]["sections"]["promptVariables"]["purposes"]["dailyFeedback"]["title"]
        in section["body"]
    )
