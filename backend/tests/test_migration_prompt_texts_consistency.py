"""マイグレーション（1be51b4ce9c0、開発Todo_単語帳_v1.0 要件C）内に転記した新文面が、
`app/init/prompt_texts_exam.py`の現在の本文と一字一句一致することを確認する。

マイグレーション自身は実行時点のappコードに依存させないため、`prompt_texts_exam`を
importせず文面をファイル内に複製する方針（ca4cefcbe9c4等と同じ）。その複製が本当に
現在の本文と一致しているかは、マイグレーションをimportしないテスト側の責務とする
（test_help_content.pyの`importlib.util.spec_from_file_location`と同じ手法でマイグレー
ションファイルをモジュールとして読み込む。マイグレーション本体はappコードをimportしない
ままで、一致検証だけをテスト側に持たせられる）。
"""

import importlib.util
from pathlib import Path

from app.init import prompt_texts_exam

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION_PATH = (
    BACKEND_ROOT
    / "alembic"
    / "versions"
    / "1be51b4ce9c0_add_glossary_to_daily_feedback_and_goal_.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("glossary_migration", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_new_daily_feedback_body_matches_prompt_texts_exam():
    migration = _load_migration_module()

    assert migration._NEW_DAILY_FEEDBACK_BODY == prompt_texts_exam.DAILY_FEEDBACK


def test_new_daily_feedback_brief_body_matches_prompt_texts_exam():
    migration = _load_migration_module()

    assert migration._NEW_DAILY_FEEDBACK_BRIEF_BODY == prompt_texts_exam.DAILY_FEEDBACK_BRIEF


def test_new_goal_consultation_body_matches_prompt_texts_exam():
    migration = _load_migration_module()

    assert migration._NEW_GOAL_CONSULTATION_BODY == prompt_texts_exam.GOAL_CONSULTATION
