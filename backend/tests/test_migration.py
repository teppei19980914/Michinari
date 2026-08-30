"""完了条件: alembic upgrade head でデータベースが構築されること。

既存データに対する安全性を検証するテスト（CODING_RULES.md「DBマイグレーションのテスト」）
は、`tests/migration_helpers.py`（`upgrade_to`）を使い、`MICHINARI_DATABASE_URL`を
一時ファイルへ切り替えた上で対象マイグレーションの前後を検証する。共有のセッション単位
テストDB（`app.database.engine`）に対して`downgrade`を行う方式は使わない
（他テストと状態を共有するリスク、および各マイグレーションの`downgrade()`実装の
正しさに依存してしまうリスクを避けるため）。
"""

import sqlite3

from alembic.config import Config
from sqlalchemy import inspect

from alembic import command
from app.database import engine
from tests import migration_helpers

EXPECTED_TABLES = {
    "app_setting",
    "prompt_template",
    "holiday",
    "day_type_default",
    "calendar_day_override",
    "resource_slot",
    "resource_slot_weekday",
    "goal",
    "exam_subject",
    "material",
    "material_subject",
    "load_profile",
    "plan_baseline",
    "daily_record",
    "study_log",
    "chat_message",
    "record_comment",
    "daily_goal_diary",
    "weekly_summary",
    "daily_message",
    "exam_result",
    "goal_retrospective",
    "ai_conversation",
    "ai_log",
    "alembic_version",
}


def test_upgrade_head_creates_all_tables():
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES <= tables


def test_upgrade_head_is_idempotent(alembic_config: Config):
    # 既にheadまで適用済みの状態で再実行してもエラーにならないこと
    command.upgrade(alembic_config, "head")
    inspector = inspect(engine)
    assert "goal" in inspector.get_table_names()


def test_material_has_planned_cycles_not_current_cycle():
    """完了条件: material に planned_cycles が存在し、current_cycle が存在しないこと。"""
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("material")}
    assert "planned_cycles" in columns
    assert "current_cycle" not in columns


def test_daily_record_no_longer_has_diary_columns():
    """完了条件: diary_body/diary_learnedはdaily_goal_diaryへ分離され、
    daily_recordには残らないこと（設計書ロジック・プロンプト編 未決事項L-04）。
    """
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("daily_record")}
    assert "diary_body" not in columns
    assert "diary_learned" not in columns
    diary_columns = {col["name"] for col in inspector.get_columns("daily_goal_diary")}
    assert diary_columns >= {"id", "daily_record_id", "goal_id", "diary_body", "diary_learned"}


def test_daily_message_has_nullable_goal_id_and_composite_unique():
    """完了条件: daily_messageがgoal_id列を持ち、(target_date, goal_id)の複合ユニーク
    制約により同一日に複数目標分のメッセージを保持できること（未決事項L-04関連）。
    """
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("daily_message")}
    assert "goal_id" in columns
    assert columns["goal_id"]["nullable"] is True
    unique_constraints = inspector.get_unique_constraints("daily_message")
    assert any(
        set(uc["column_names"]) == {"target_date", "goal_id"} for uc in unique_constraints
    )


def test_daily_goal_diary_migration_attributes_shared_diary_by_goal(tmp_path, monkeypatch):
    """未決事項L-04の移行ロジック（9a1c3e7d5b2f）を、既存データがある状態への適用として
    検証する（CODING_RULES.md「DBマイグレーションのテスト」）。

      1. その日のstudy_logが単一目標のみ → その目標へ1件
      2. その日のstudy_logが複数目標にまたがる → 関与した全目標へ複製
      3. その日のstudy_logが無い（バッファ日等） → 日付時点で活動中の全目標へ複製（フォールバック）
    """
    db_path = tmp_path / "daily_goal_diary_migration.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("f3a1b8c6d9e2")  # daily_goal_diary分離（head）の1つ前

    now = "2026-01-01T00:00:00"
    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO goal (name, start_date, status, resource_ratio, updated_at, "
            "created_at) VALUES ('目標A', '2026-01-01', 'ACTIVE', 0, ?, ?)",
            (now, now),
        )
        goal_a_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO goal (name, start_date, status, resource_ratio, updated_at, "
            "created_at) VALUES ('目標B', '2026-01-01', 'ACTIVE', 0, ?, ?)",
            (now, now),
        )
        goal_b_id = cursor.lastrowid

        def insert_material(goal_id: int, name: str) -> int:
            cursor.execute(
                "INSERT INTO material (goal_id, name, unit_label, total_amount, "
                "planned_cycles, start_date, due_date, due_date_is_manual, "
                "required_environment, quality_metric_type, is_active, display_order, "
                "updated_at, created_at) VALUES (?, ?, 'ページ', 100, 1, '2026-01-01', "
                "'2026-12-31', 1, 'ANY', 'NONE', 1, 1, ?, ?)",
                (goal_id, name, now, now),
            )
            return cursor.lastrowid

        material_a_id = insert_material(goal_a_id, "教材A")
        material_b_id = insert_material(goal_b_id, "教材B")

        def insert_record(record_date: str, diary_body: str, diary_learned: str) -> int:
            cursor.execute(
                "INSERT INTO daily_record (record_date, record_state, diary_body, "
                "diary_learned, created_at) VALUES (?, 'REPORTED', ?, ?, ?)",
                (record_date, diary_body, diary_learned, now),
            )
            return cursor.lastrowid

        def insert_study_log(record_id: int, material_id: int) -> None:
            cursor.execute(
                "INSERT INTO study_log (daily_record_id, material_id, amount_completed, "
                "cycle_number, created_at) VALUES (?, ?, 10, 1, ?)",
                (record_id, material_id, now),
            )

        # ケース1: 単一目標のみ関与した日
        record_single_id = insert_record("2026-03-10", "共有日記1", "学び1")
        insert_study_log(record_single_id, material_a_id)

        # ケース2: 複数目標が同日に関与した日
        record_multi_id = insert_record("2026-03-11", "共有日記2", "学び2")
        insert_study_log(record_multi_id, material_a_id)
        insert_study_log(record_multi_id, material_b_id)

        # ケース3: study_logが無い日（バッファ日等、活動中の全目標へフォールバック）
        record_fallback_id = insert_record("2026-03-12", "共有日記3", "学び3")

        connection.commit()
    finally:
        connection.close()

    migration_helpers.upgrade_to("head")

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT daily_record_id, goal_id, diary_body, diary_learned FROM daily_goal_diary "
            "WHERE daily_record_id IN (?, ?, ?)",
            (record_single_id, record_multi_id, record_fallback_id),
        ).fetchall()
    finally:
        connection.close()

    by_record: dict[int, list[tuple]] = {}
    for row in rows:
        by_record.setdefault(row[0], []).append(row)

    single_rows = by_record[record_single_id]
    assert {row[1] for row in single_rows} == {goal_a_id}
    assert single_rows[0][2] == "共有日記1"
    assert single_rows[0][3] == "学び1"

    multi_rows = by_record[record_multi_id]
    assert {row[1] for row in multi_rows} == {goal_a_id, goal_b_id}
    assert all(row[2] == "共有日記2" for row in multi_rows)

    fallback_rows = by_record[record_fallback_id]
    assert {row[1] for row in fallback_rows} == {goal_a_id, goal_b_id}
    assert all(row[2] == "共有日記3" for row in fallback_rows)


def test_daily_message_migration_preserves_legacy_rows_as_goal_independent(tmp_path, monkeypatch):
    """未決事項L-04の移行ロジック（c7d391a6f0e5）を、既存データがある状態への適用として
    検証する。目標別生成に切り替える前の共有メッセージ（旧スキーマ）は、特定の目標が
    書いたと偽ることのないよう、複製せずgoal_id=NULLのまま引き継がれること。
    """
    db_path = tmp_path / "daily_message_migration.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("b4c8e2f19a3d")  # daily_message目標別分離（head）の1つ前

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO daily_message (target_date, body, generated_at) "
            "VALUES ('2026-04-01', '旧仕様の共有メッセージ', '2026-04-01T00:00:00')"
        )
        connection.commit()
    finally:
        connection.close()

    migration_helpers.upgrade_to("head")

    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT goal_id, body FROM daily_message WHERE target_date = '2026-04-01'"
        ).fetchone()
    finally:
        connection.close()

    assert row[0] is None
    assert row[1] == "旧仕様の共有メッセージ"


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

    migration_helpers.upgrade_to("head")

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
