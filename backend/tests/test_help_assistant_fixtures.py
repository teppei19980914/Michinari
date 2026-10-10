"""ヘルプAIアシスタントの実機検証用質問セット（開発Todo §8）の構造を固定する。

`fixtures/help_assistant/question_set.json` はNewtonXへの実通信を要する実機検証（開発Todo
`開発Todo_ヘルプAIアシスタント_v1.0.md` §6）の入力であり、CIでは実行しない（自動テストでは
ファイルの構造が壊れていないことのみを検証する）。
"""

import json
from pathlib import Path

FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "help_assistant" / "question_set.json"
)


def _load() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_question_set_has_all_categories_with_minimum_count():
    data = _load()
    for category in ("in_scope", "out_of_scope", "paraphrase", "injection"):
        assert len(data[category]) >= 10, f"{category} has fewer than 10 questions"


def test_in_scope_questions_cite_real_help_sections():
    from app.services.help_content import load_sections

    known_ids = {section.id for section in load_sections()}
    data = _load()
    for item in data["in_scope"]:
        assert item["expected_section_id"] in known_ids, item["question"]


def test_no_duplicate_questions_within_a_category():
    data = _load()
    for category in ("in_scope", "out_of_scope", "paraphrase", "injection"):
        questions = [item["question"] for item in data[category]]
        assert len(questions) == len(set(questions)), f"duplicate question in {category}"


def test_no_question_text_repeated_across_categories():
    data = _load()
    all_questions = [
        item["question"]
        for category in ("in_scope", "out_of_scope", "paraphrase", "injection")
        for item in data[category]
    ]
    assert len(all_questions) == len(set(all_questions))
