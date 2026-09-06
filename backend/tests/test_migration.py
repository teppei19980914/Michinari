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
    "book",
    "daily_record",
    "study_log",
    "reading_log",
    "chat_message",
    "record_comment",
    "daily_goal_diary",
    "weekly_summary",
    "daily_message",
    "exam_result",
    "goal_retrospective",
    "ai_conversation",
    "ai_log",
    "work_assignment",
    "work_log",
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


def test_goal_has_category_column_and_existing_rows_backfilled_to_exam(db_session):
    """完了条件: goal.categoryが存在し、既存goalレコードがEXAMとして引き継がれること。"""
    import datetime as dt

    from app.constants.enums import GoalCategory, GoalStatus
    from app.models.goal import Goal

    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("goal")}
    assert "category" in columns

    goal = Goal(
        name="マイグレーション検証用", start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE
    )
    db_session.add(goal)
    db_session.commit()
    assert goal.category == GoalCategory.EXAM


def test_chat_message_has_purpose_column_defaulting_to_daily_feedback(db_session):
    """完了条件: chat_message.purposeが存在し、既存の用途（資格試験）ではDAILY_FEEDBACKとして
    引き継がれること（実装フェーズ分割計画書Phase16）。"""
    import datetime as dt

    from app.constants.enums import AiPurpose, ChatRole, RecordState
    from app.models.record import ChatMessage, DailyRecord

    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("chat_message")}
    assert "purpose" in columns

    record = DailyRecord(
        record_date=dt.date(2026, 1, 1), exam_record_state=RecordState.PROGRESS_ONLY
    )
    db_session.add(record)
    db_session.flush()
    message = ChatMessage(
        daily_record_id=record.id, role=ChatRole.ASSISTANT, content="応答", sequence=1
    )
    db_session.add(message)
    db_session.commit()
    assert message.purpose == AiPurpose.DAILY_FEEDBACK


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


def test_daily_record_has_category_state_columns_and_no_longer_has_record_state():
    """完了条件: daily_recordがカテゴリ別の確定状態6列を持ち、旧record_state/reported_at
    列は残っていないこと（仕様変更2026-09-05、7c2e5a1d9f4b）。"""
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("daily_record")}
    assert columns >= {
        "exam_record_state",
        "exam_reported_at",
        "reading_record_state",
        "reading_reported_at",
        "work_record_state",
        "work_reported_at",
    }
    assert "record_state" not in columns
    assert "reported_at" not in columns


def test_daily_message_has_nullable_goal_id_and_composite_unique():
    """完了条件: daily_messageがgoal_id列を持ち、(target_date, goal_id)の複合ユニーク
    制約により同一日に複数目標分のメッセージを保持できること（未決事項L-04関連）。
    """
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("daily_message")}
    assert "goal_id" in columns
    assert columns["goal_id"]["nullable"] is True
    unique_constraints = inspector.get_unique_constraints("daily_message")
    assert any(set(uc["column_names"]) == {"target_date", "goal_id"} for uc in unique_constraints)


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


def test_work_goal_category_migration_creates_work_tables_and_retrospective_columns():
    """完了条件: work_assignment・work_logテーブルが作成され、goal_retrospectiveに
    period_type以下9列が追加されること（実装フェーズ分割計画書Phase20、e1f4a9c3b6d8）。"""
    inspector = inspect(engine)

    work_assignment_columns = {col["name"] for col in inspector.get_columns("work_assignment")}
    assert work_assignment_columns >= {
        "id",
        "goal_id",
        "client_name",
        "expected_content",
        "start_date",
        "created_at",
        "updated_at",
    }
    work_assignment_unique = inspector.get_unique_constraints("work_assignment")
    assert any(uc["column_names"] == ["goal_id"] for uc in work_assignment_unique)

    work_log_columns = {col["name"] for col in inspector.get_columns("work_log")}
    assert work_log_columns >= {
        "id",
        "daily_record_id",
        "work_assignment_id",
        "body",
        "created_at",
    }
    work_log_unique = inspector.get_unique_constraints("work_log")
    assert any(
        set(uc["column_names"]) == {"work_assignment_id", "daily_record_id"}
        for uc in work_log_unique
    )

    retrospective_columns = {col["name"] for col in inspector.get_columns("goal_retrospective")}
    assert retrospective_columns >= {
        "period_type",
        "period_key",
        "target_goal_text",
        "business_summary",
        "achievement_score",
        "achievement_reflection",
        "next_goal_text",
        "report_notes",
        "edited_at",
    }
    retrospective_unique = inspector.get_unique_constraints("goal_retrospective")
    assert any(
        set(uc["column_names"]) == {"goal_id", "period_type", "period_key", "is_anonymized"}
        for uc in retrospective_unique
    )


def test_goal_retrospective_migration_preserves_existing_exam_rows_with_data(tmp_path, monkeypatch):
    """goal_retrospectiveへの9列追加マイグレーション（e1f4a9c3b6d8）を、既存データ
    （EXAM総括レポート想定の行、period_type等の概念が無かった旧スキーマ行）がある状態への
    適用として検証する（CODING_RULES.md「DBマイグレーションのテスト」）。列追加後も
    既存行のbody等が保持され、新設列はNULLとして引き継がれることを確認する。
    """
    db_path = tmp_path / "goal_retrospective_migration.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("9723ab049ecd")  # work列追加（head）の1つ前

    now = "2026-01-01T00:00:00"
    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO goal (name, start_date, status, resource_ratio, category, "
            "updated_at, created_at) VALUES ('既存資格目標', '2026-01-01', 'ACTIVE', 1.0, "
            "'EXAM', ?, ?)",
            (now, now),
        )
        goal_id = cursor.lastrowid

        # 既存のEXAM総括レポート行を複数件（再生成による複数レコード）挿入する
        cursor.execute(
            "INSERT INTO goal_retrospective (goal_id, body, is_anonymized, generated_at) "
            "VALUES (?, '旧スキーマでの総括レポート1回目', 0, ?)",
            (goal_id, now),
        )
        first_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO goal_retrospective (goal_id, body, is_anonymized, generated_at) "
            "VALUES (?, '旧スキーマでの総括レポート2回目（再生成）', 0, ?)",
            (goal_id, now),
        )
        second_id = cursor.lastrowid
        connection.commit()
    finally:
        connection.close()

    migration_helpers.upgrade_to("head")

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT id, body, period_type, period_key, achievement_score, edited_at "
            "FROM goal_retrospective WHERE id IN (?, ?)",
            (first_id, second_id),
        ).fetchall()
    finally:
        connection.close()

    by_id = {row[0]: row for row in rows}
    assert by_id[first_id][1] == "旧スキーマでの総括レポート1回目"
    assert by_id[second_id][1] == "旧スキーマでの総括レポート2回目（再生成）"
    # 新設列はいずれもNULLのまま引き継がれる（遡及設定なし。Phase20注意点）
    for row in rows:
        assert row[2] is None  # period_type
        assert row[3] is None  # period_key
        assert row[4] is None  # achievement_score
        assert row[5] is None  # edited_at


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


def test_daily_record_category_state_migration_backfills_by_category_presence(
    tmp_path, monkeypatch
):
    """確定状態のカテゴリ別分割マイグレーション（7c2e5a1d9f4b）を、既存データがある状態への
    適用として検証する（CODING_RULES.md「DBマイグレーションのテスト」）。旧モデルは日付単位
    でしか確定状態を持たなかったため、「そのカテゴリに該当するログ／日記／AI対話が存在する
    場合のみ」旧record_state/reported_atを引き継ぐベストエフォート移行になる。
    """
    db_path = tmp_path / "daily_record_category_state_migration.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("e1f4a9c3b6d8")  # カテゴリ別確定状態分離（head）の1つ前

    now = "2026-01-01T00:00:00"
    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO goal (name, start_date, status, resource_ratio, category, "
            "updated_at, created_at) VALUES ('資格目標', '2026-01-01', 'ACTIVE', 1.0, "
            "'EXAM', ?, ?)",
            (now, now),
        )
        exam_goal_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO material (goal_id, name, unit_label, total_amount, "
            "planned_cycles, start_date, due_date, due_date_is_manual, "
            "required_environment, quality_metric_type, is_active, display_order, "
            "updated_at, created_at) VALUES (?, '教材A', 'ページ', 100, 1, '2026-01-01', "
            "'2026-12-31', 1, 'ANY', 'NONE', 1, 1, ?, ?)",
            (exam_goal_id, now, now),
        )
        material_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO goal (name, start_date, status, resource_ratio, category, "
            "updated_at, created_at) VALUES ('読書目標', '2026-01-01', 'ACTIVE', 0, "
            "'READING', ?, ?)",
            (now, now),
        )
        reading_goal_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO book (goal_id, title, start_date, due_date, updated_at, created_at) "
            "VALUES (?, '書籍A', '2026-01-01', '2026-12-31', ?, ?)",
            (reading_goal_id, now, now),
        )
        book_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO goal (name, start_date, status, resource_ratio, category, "
            "updated_at, created_at) VALUES ('仕事目標', '2026-01-01', 'ACTIVE', 0, "
            "'WORK', ?, ?)",
            (now, now),
        )
        work_goal_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO work_assignment (goal_id, expected_content, start_date, "
            "updated_at, created_at) VALUES (?, '想定業務内容', '2026-01-01', ?, ?)",
            (work_goal_id, now, now),
        )
        work_assignment_id = cursor.lastrowid

        def insert_record(record_date: str, record_state: str) -> int:
            cursor.execute(
                "INSERT INTO daily_record (record_date, record_state, reported_at, "
                "created_at) VALUES (?, ?, ?, ?)",
                (record_date, record_state, now if record_state == "REPORTED" else None, now),
            )
            return cursor.lastrowid

        # ケース1: study_logのみ（EXAM）、REPORTED
        record_exam_id = insert_record("2026-03-01", "REPORTED")
        cursor.execute(
            "INSERT INTO study_log (daily_record_id, material_id, amount_completed, "
            "cycle_number, created_at) VALUES (?, ?, 10, 1, ?)",
            (record_exam_id, material_id, now),
        )

        # ケース2: reading_logのみ、PROGRESS_ONLY（未確定はreported_atを引き継がない）
        record_reading_id = insert_record("2026-03-02", "PROGRESS_ONLY")
        cursor.execute(
            "INSERT INTO reading_log (daily_record_id, book_id, recall_body, created_at) "
            "VALUES (?, ?, '想起', ?)",
            (record_reading_id, book_id, now),
        )

        # ケース3: work_logのみ、REPORTED
        record_work_id = insert_record("2026-03-03", "REPORTED")
        cursor.execute(
            "INSERT INTO work_log (daily_record_id, work_assignment_id, body, created_at) "
            "VALUES (?, ?, '業務内容', ?)",
            (record_work_id, work_assignment_id, now),
        )

        # ケース4: study_log + work_log（複数カテゴリが同日に同時進行）、REPORTED
        record_multi_id = insert_record("2026-03-04", "REPORTED")
        cursor.execute(
            "INSERT INTO study_log (daily_record_id, material_id, amount_completed, "
            "cycle_number, created_at) VALUES (?, ?, 5, 1, ?)",
            (record_multi_id, material_id, now),
        )
        cursor.execute(
            "INSERT INTO work_log (daily_record_id, work_assignment_id, body, created_at) "
            "VALUES (?, ?, '業務内容2', ?)",
            (record_multi_id, work_assignment_id, now),
        )

        # ケース5: 実績ログは無いがchat_message(DAILY_FEEDBACK)のみ存在、PROGRESS_ONLY
        # （AI対話は確定前でも実行できるため、実績0件の日もEXAMに触れたとみなす）
        record_chat_only_id = insert_record("2026-03-05", "PROGRESS_ONLY")
        cursor.execute(
            "INSERT INTO chat_message (daily_record_id, purpose, role, content, sequence, "
            "created_at) VALUES (?, 'DAILY_FEEDBACK', 'ASSISTANT', '応答', 1, ?)",
            (record_chat_only_id, now),
        )

        connection.commit()
    finally:
        connection.close()

    migration_helpers.upgrade_to("head")

    connection = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(daily_record)")}
        rows = {
            row[0]: row[1:]
            for row in connection.execute(
                "SELECT id, exam_record_state, exam_reported_at, reading_record_state, "
                "reading_reported_at, work_record_state, work_reported_at FROM daily_record "
                "WHERE id IN (?, ?, ?, ?, ?)",
                (
                    record_exam_id,
                    record_reading_id,
                    record_work_id,
                    record_multi_id,
                    record_chat_only_id,
                ),
            )
        }
    finally:
        connection.close()

    assert "record_state" not in columns
    assert "reported_at" not in columns

    exam_state, exam_reported_at, reading_state, _, work_state, _ = rows[record_exam_id]
    assert exam_state == "REPORTED"
    assert exam_reported_at is not None
    assert reading_state is None
    assert work_state is None

    _, _, reading_state, reading_reported_at, work_state, _ = rows[record_reading_id]
    assert reading_state == "PROGRESS_ONLY"
    assert reading_reported_at is None
    assert work_state is None

    exam_state, _, reading_state, _, work_state, work_reported_at = rows[record_work_id]
    assert work_state == "REPORTED"
    assert work_reported_at is not None
    assert exam_state is None
    assert reading_state is None

    exam_state, _, reading_state, _, work_state, _ = rows[record_multi_id]
    assert exam_state == "REPORTED"
    assert work_state == "REPORTED"
    assert reading_state is None  # 触れていないカテゴリはNULLのまま

    exam_state, _, reading_state, _, work_state, _ = rows[record_chat_only_id]
    assert exam_state == "PROGRESS_ONLY"  # chat_messageのみでもEXAMに触れたとみなす
    assert reading_state is None
    assert work_state is None


def test_chat_message_has_nullable_goal_id_column(db_session):
    """完了条件: chat_message.goal_idが存在し、NULL許容であること
    （Phase26、d8f21a6c4b3e、未決事項L-07の解消方針転換）。"""
    import datetime as dt

    from app.constants.enums import ChatRole, RecordState
    from app.models.record import ChatMessage, DailyRecord

    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("chat_message")}
    assert "goal_id" in columns
    assert columns["goal_id"]["nullable"] is True

    record = DailyRecord(
        record_date=dt.date(2026, 1, 1), exam_record_state=RecordState.PROGRESS_ONLY
    )
    db_session.add(record)
    db_session.flush()
    message = ChatMessage(
        daily_record_id=record.id, role=ChatRole.ASSISTANT, content="応答", sequence=1
    )
    db_session.add(message)
    db_session.commit()
    assert message.goal_id is None


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
