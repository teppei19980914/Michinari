"""完了条件: alembic upgrade head でデータベースが構築されること（prompt_template移行系）。

本ファイルは既存データに対する安全性を検証するテスト（CODING_RULES.md「DBマイグレーション
のテスト」）のうち、prompt_templateの初期文面移行（利用者がカスタマイズ済みの文面は
上書きしない・未カスタマイズの文面は新文面へ更新する）を対象とする。`tests/migration_helpers.py`
（`upgrade_to`）を使い、`MICHINARI_DATABASE_URL`を一時ファイルへ切り替えた上で対象マイグレー
ションの前後を検証する。他テーブルのデータ移行はtest_migration_data.py、最終スキーマの構造
検証はtest_migration_schema.pyを参照（実装フェーズ分割計画書S02、test_migration.pyからの分割）。
"""

import sqlite3

import pytest

from tests import migration_helpers


def test_daily_feedback_prompt_migration_updates_non_customized_template(tmp_path, monkeypatch):
    """AIチャットの目標混同リスク対応（b4c8e2f19a3d）を、既存データがある状態への適用として
    検証する。is_customized=False（ユーザーが未編集）のDAILY_FEEDBACKテンプレートは、
    「複数目標がある場合の注意」セクションを含む新文面へ更新されること。
    """
    db_path = tmp_path / "prompt_migration_non_customized.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("9a1c3e7d5b2f")  # プロンプト更新（head）の1つ前

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES ('DAILY_FEEDBACK', '旧文面（移行前）', 0, '2026-01-01T00:00:00')"
        )
        connection.commit()
    finally:
        connection.close()

    # b4c8e2f19a3d自体の効果を検証する（head全体ではない）。後続のc1a5f9e3d7b2
    # （Phase26、目標単位分離に伴い本セクションを削除）で再び上書きされるため。
    migration_helpers.upgrade_to("b4c8e2f19a3d")

    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = 'DAILY_FEEDBACK'"
        ).fetchone()
    finally:
        connection.close()

    assert "複数目標がある場合の注意" in row[0]


def test_daily_feedback_prompt_migration_preserves_customized_template(tmp_path, monkeypatch):
    """is_customized=True（Settings画面でユーザーが手動編集済み）のテンプレートは
    上書きしないこと（settings_service.update_prompt_templateが立てるフラグを尊重）。
    """
    db_path = tmp_path / "prompt_migration_customized.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("9a1c3e7d5b2f")  # プロンプト更新（head）の1つ前

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES ('DAILY_FEEDBACK', 'ユーザーがカスタマイズした文面', 1, '2026-01-01T00:00:00')"
        )
        connection.commit()
    finally:
        connection.close()

    migration_helpers.upgrade_to("head")

    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = 'DAILY_FEEDBACK'"
        ).fetchone()
    finally:
        connection.close()

    assert row[0] == "ユーザーがカスタマイズした文面"


def test_daily_feedback_prompt_removal_migration_updates_non_customized_template(
    tmp_path, monkeypatch
):
    """目標単位分離（c1a5f9e3d7b2、Phase26）に伴う「複数目標がある場合の注意」削除を、
    既存データがある状態への適用として検証する。is_customized=False（利用者が未編集）の
    テンプレートは、当該セクションを含まない新文面へ更新されること。
    """
    db_path = tmp_path / "prompt_removal_migration_non_customized.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("d8f21a6c4b3e")  # 削除マイグレーション（head）の1つ前

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES ('DAILY_FEEDBACK', '旧文面（複数目標がある場合の注意を含む）', 0, "
            "'2026-01-01T00:00:00')"
        )
        connection.commit()
    finally:
        connection.close()

    migration_helpers.upgrade_to("head")

    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = 'DAILY_FEEDBACK'"
        ).fetchone()
    finally:
        connection.close()

    assert "複数目標がある場合の注意" not in row[0]


def test_daily_feedback_prompt_removal_migration_preserves_customized_template(
    tmp_path, monkeypatch
):
    """is_customized=True（利用者が手動編集済み）のテンプレートは、削除マイグレーション
    （c1a5f9e3d7b2）でも上書きしないこと。"""
    db_path = tmp_path / "prompt_removal_migration_customized.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("d8f21a6c4b3e")  # 削除マイグレーション（head）の1つ前

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES ('DAILY_FEEDBACK', "
            "'ユーザーがカスタマイズした文面（複数目標がある場合の注意を含む）', 1, "
            "'2026-01-01T00:00:00')"
        )
        connection.commit()
    finally:
        connection.close()

    migration_helpers.upgrade_to("head")

    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = 'DAILY_FEEDBACK'"
        ).fetchone()
    finally:
        connection.close()

    assert row[0] == "ユーザーがカスタマイズした文面（複数目標がある場合の注意を含む）"


_WEEKLY_SUMMARIES_PROMPT_PURPOSES = (
    "DAILY_FEEDBACK_READING",
    "DAILY_FEEDBACK_WORK",
    "GOAL_RETROSPECTIVE_READING",
    "GOAL_RETROSPECTIVE_WORK_MONTHLY",
    "GOAL_RETROSPECTIVE_WORK_SEMIANNUAL",
)


@pytest.mark.parametrize("purpose", _WEEKLY_SUMMARIES_PROMPT_PURPOSES)
def test_weekly_summaries_prompt_migration_updates_non_customized_template(
    tmp_path, monkeypatch, purpose
):
    """L-11（f7c3e9a1b5d6）: 読書・仕事の日次報告フィードバックと総括レポート系5用途に
    {{weekly_summaries}}を追加するマイグレーションを、既存データがある状態への適用として
    検証する。is_customized=False（利用者が未編集）のテンプレートは、{{weekly_summaries}}
    を含む新文面へ更新されること（c1a5f9e3d7b2の同名テストと同じ方針）。
    """
    db_path = tmp_path / f"weekly_summaries_prompt_migration_non_customized_{purpose}.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("a9e3c5b71d64")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES (?, '旧文面（{{weekly_summaries}}を含まない）', 0, '2026-01-01T00:00:00')",
            (purpose,),
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = ?", (purpose,)
        ).fetchone()

    assert "{{weekly_summaries}}" in row[0]


@pytest.mark.parametrize("purpose", _WEEKLY_SUMMARIES_PROMPT_PURPOSES)
def test_weekly_summaries_prompt_migration_preserves_customized_template(
    tmp_path, monkeypatch, purpose
):
    """is_customized=True（利用者が手動編集済み）のテンプレートは、本マイグレーション
    （f7c3e9a1b5d6）でも上書きしないこと。"""
    db_path = tmp_path / f"weekly_summaries_prompt_migration_customized_{purpose}.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("a9e3c5b71d64")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES (?, 'ユーザーがカスタマイズした文面', 1, '2026-01-01T00:00:00')",
            (purpose,),
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = ?", (purpose,)
        ).fetchone()

    assert row[0] == "ユーザーがカスタマイズした文面"


_PERSPECTIVE_SUGGESTION_PROMPT_PURPOSES = (
    "DAILY_FEEDBACK",
    "DAILY_FEEDBACK_READING",
    "DAILY_FEEDBACK_WORK",
)


@pytest.mark.parametrize("purpose", _PERSPECTIVE_SUGGESTION_PROMPT_PURPOSES)
def test_perspective_suggestion_prompt_migration_updates_non_customized_template(
    tmp_path, monkeypatch, purpose
):
    """S-4 4-3（7f4f5e089f3a）: 資格試験・読書・仕事の日次報告フィードバックへ
    {{perspective_suggestion}}を追加するマイグレーションを、既存データがある状態への
    適用として検証する。is_customized=False（利用者が未編集）のテンプレートは、
    {{perspective_suggestion}}を含む新文面へ更新されること（f7c3e9a1b5d6の同名テストと
    同じ方針）。
    """
    db_path = tmp_path / f"perspective_suggestion_prompt_migration_non_customized_{purpose}.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("f7c3e9a1b5d6")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES (?, ?, 0, '2026-01-01T00:00:00')",
            (purpose, "旧文面（{{perspective_suggestion}}を含まない）"),
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = ?", (purpose,)
        ).fetchone()

    assert "{{perspective_suggestion}}" in row[0]


@pytest.mark.parametrize("purpose", _PERSPECTIVE_SUGGESTION_PROMPT_PURPOSES)
def test_perspective_suggestion_prompt_migration_preserves_customized_template(
    tmp_path, monkeypatch, purpose
):
    """is_customized=True（利用者が手動編集済み）のテンプレートは、本マイグレーション
    （7f4f5e089f3a）でも上書きしないこと。"""
    db_path = tmp_path / f"perspective_suggestion_prompt_migration_customized_{purpose}.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("f7c3e9a1b5d6")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES (?, 'ユーザーがカスタマイズした文面', 1, '2026-01-01T00:00:00')",
            (purpose,),
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = ?", (purpose,)
        ).fetchone()

    assert row[0] == "ユーザーがカスタマイズした文面"


def test_recent_logs_prompt_migration_updates_non_customized_template(tmp_path, monkeypatch):
    """S04 G2（ca4cefcbe9c4）: 資格試験の日次報告フィードバックへ{{recent_logs}}を
    追加するマイグレーションを、既存データがある状態への適用として検証する。
    is_customized=False（利用者が未編集）のテンプレートは、{{recent_logs}}を含む
    新文面へ更新されること。
    """
    db_path = tmp_path / "recent_logs_prompt_migration_non_customized.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("b8e4d1f7a3c9")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES ('DAILY_FEEDBACK', '旧文面（{{recent_logs}}を含まない）', 0, "
            "'2026-01-01T00:00:00')"
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = 'DAILY_FEEDBACK'"
        ).fetchone()

    assert "{{recent_logs}}" in row[0]


def test_recent_logs_prompt_migration_preserves_customized_template(tmp_path, monkeypatch):
    """is_customized=True（利用者が手動編集済み）のテンプレートは、本マイグレーション
    （ca4cefcbe9c4）でも上書きしないこと。"""
    db_path = tmp_path / "recent_logs_prompt_migration_customized.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("b8e4d1f7a3c9")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES ('DAILY_FEEDBACK', 'ユーザーがカスタマイズした文面', 1, "
            "'2026-01-01T00:00:00')"
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = 'DAILY_FEEDBACK'"
        ).fetchone()

    assert row[0] == "ユーザーがカスタマイズした文面"


_CONVERSATION_CONTINUITY_PROMPT_PURPOSES = (
    "DAILY_FEEDBACK",
    "DAILY_FEEDBACK_READING",
    "DAILY_FEEDBACK_WORK",
)


@pytest.mark.parametrize("purpose", _CONVERSATION_CONTINUITY_PROMPT_PURPOSES)
def test_conversation_continuity_prompt_migration_updates_non_customized_template(
    tmp_path, monkeypatch, purpose
):
    """継続対話でも毎回「本日は」から始まる状況の再要約を繰り返してしまう事象への対応
    （2fd46bbc5070）を、既存データがある状態への適用として検証する。is_customized=False
    （利用者が未編集）のテンプレートは、{{conversation_history}}に既にやり取りがある場合の
    振る舞いを指示する新文面へ更新されること（7f4f5e089f3aの同名テストと同じ方針）。
    """
    db_path = tmp_path / f"conversation_continuity_prompt_migration_non_customized_{purpose}.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("6f0e82a9c518")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES (?, ?, 0, '2026-01-01T00:00:00')",
            (purpose, "旧文面（継続対話への言及を含まない）"),
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = ?", (purpose,)
        ).fetchone()

    assert "直接応答することを優先してください" in row[0]


@pytest.mark.parametrize("purpose", _CONVERSATION_CONTINUITY_PROMPT_PURPOSES)
def test_conversation_continuity_prompt_migration_preserves_customized_template(
    tmp_path, monkeypatch, purpose
):
    """is_customized=True（利用者が手動編集済み）のテンプレートは、本マイグレーション
    （2fd46bbc5070）でも上書きしないこと。"""
    db_path = tmp_path / f"conversation_continuity_prompt_migration_customized_{purpose}.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("6f0e82a9c518")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES (?, 'ユーザーがカスタマイズした文面', 1, '2026-01-01T00:00:00')",
            (purpose,),
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = ?", (purpose,)
        ).fetchone()

    assert row[0] == "ユーザーがカスタマイズした文面"


#: S07 G6・G7（0ad4f28cd909）: 対象purposeと、新文面に含まれるはずの新変数の組。
_WEEKLY_LOGS_PROMPT_TARGETS = (
    ("GOAL_RETROSPECTIVE", "{{recent_logs}}"),
    ("EVALUATION_REPORT_WORK", "{{weekly_summaries}}"),
)


@pytest.mark.parametrize("purpose,new_variable", _WEEKLY_LOGS_PROMPT_TARGETS)
def test_weekly_logs_prompt_migration_updates_non_customized_template(
    tmp_path, monkeypatch, purpose, new_variable
):
    """S07 G6・G7（0ad4f28cd909）: 資格の総括レポートへ{{recent_logs}}、仕事のAI評価
    レポートへ{{weekly_summaries}}を追加するマイグレーションを、既存データがある状態への
    適用として検証する。is_customized=False（利用者が未編集）のテンプレートは、新変数を
    含む新文面へ更新されること。
    """
    db_path = tmp_path / f"weekly_logs_prompt_migration_non_customized_{purpose}.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("ca4cefcbe9c4")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES (?, ?, 0, '2026-01-01T00:00:00')",
            (purpose, f"旧文面（{new_variable}を含まない）"),
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = ?", (purpose,)
        ).fetchone()

    assert new_variable in row[0]


@pytest.mark.parametrize("purpose,new_variable", _WEEKLY_LOGS_PROMPT_TARGETS)
def test_weekly_logs_prompt_migration_preserves_customized_template(
    tmp_path, monkeypatch, purpose, new_variable
):
    """is_customized=True（利用者が手動編集済み）のテンプレートは、本マイグレーション
    （0ad4f28cd909）でも上書きしないこと。"""
    db_path = tmp_path / f"weekly_logs_prompt_migration_customized_{purpose}.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("ca4cefcbe9c4")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES (?, 'ユーザーがカスタマイズした文面', 1, '2026-01-01T00:00:00')",
            (purpose,),
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = ?", (purpose,)
        ).fetchone()

    assert row[0] == "ユーザーがカスタマイズした文面"


#: S08 G5（9d3d5631a940）: 週次要約3カテゴリ分の対象purpose。
_WEEK_CHAT_PROMPT_PURPOSES = (
    "WEEKLY_SUMMARY",
    "WEEKLY_SUMMARY_READING",
    "WEEKLY_SUMMARY_WORK",
)


@pytest.mark.parametrize("purpose", _WEEK_CHAT_PROMPT_PURPOSES)
def test_week_chat_prompt_migration_updates_non_customized_template(
    tmp_path, monkeypatch, purpose
):
    """S08 G5（9d3d5631a940）: 資格・読書・仕事の週次要約へ{{week_chat}}（週内のAIとの対話の
    うち利用者本人の発言）を追加するマイグレーションを、既存データがある状態への適用として
    検証する。is_customized=False（利用者が未編集）のテンプレートは、{{week_chat}}を含む
    新文面へ更新されること。
    """
    db_path = tmp_path / f"week_chat_prompt_migration_non_customized_{purpose}.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("0ad4f28cd909")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES (?, '旧文面（{{week_chat}}を含まない）', 0, '2026-01-01T00:00:00')",
            (purpose,),
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = ?", (purpose,)
        ).fetchone()

    assert "{{week_chat}}" in row[0]


@pytest.mark.parametrize("purpose", _WEEK_CHAT_PROMPT_PURPOSES)
def test_week_chat_prompt_migration_preserves_customized_template(
    tmp_path, monkeypatch, purpose
):
    """is_customized=True（利用者が手動編集済み）のテンプレートは、本マイグレーション
    （9d3d5631a940）でも上書きしないこと。"""
    db_path = tmp_path / f"week_chat_prompt_migration_customized_{purpose}.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("0ad4f28cd909")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES (?, 'ユーザーがカスタマイズした文面', 1, '2026-01-01T00:00:00')",
            (purpose,),
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = ?", (purpose,)
        ).fetchone()

    assert row[0] == "ユーザーがカスタマイズした文面"


def test_exam_results_prompt_migration_updates_non_customized_template(tmp_path, monkeypatch):
    """dfef541d349f: 資格試験の日次報告フィードバックへ{{exam_results}}（科目ごとの合否と
    得点）を追加するマイグレーションを、既存データがある状態への適用として検証する。
    科目Aのみ合格登録済みで科目Bが未登録のまま目標が継続する二段階試験でも、AIが科目単位の
    合否を事実として把握できるようにする設計変更（is_customized=Falseの行のみ対象）。
    """
    db_path = tmp_path / "exam_results_prompt_migration_non_customized.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("9d3d5631a940")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES ('DAILY_FEEDBACK', '旧文面（{{exam_results}}を含まない）', 0, "
            "'2026-01-01T00:00:00')"
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = 'DAILY_FEEDBACK'"
        ).fetchone()

    assert "{{exam_results}}" in row[0]


def test_exam_results_prompt_migration_preserves_customized_template(tmp_path, monkeypatch):
    """is_customized=True（利用者が手動編集済み）のテンプレートは、本マイグレーション
    （dfef541d349f）でも上書きしないこと。"""
    db_path = tmp_path / "exam_results_prompt_migration_customized.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("9d3d5631a940")  # 本マイグレーション（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO prompt_template (purpose, body, is_customized, updated_at) "
            "VALUES ('DAILY_FEEDBACK', 'ユーザーがカスタマイズした文面', 1, "
            "'2026-01-01T00:00:00')"
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        row = connection.execute(
            "SELECT body FROM prompt_template WHERE purpose = 'DAILY_FEEDBACK'"
        ).fetchone()

    assert row[0] == "ユーザーがカスタマイズした文面"
