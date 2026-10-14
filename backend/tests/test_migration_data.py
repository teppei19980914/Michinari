"""完了条件: alembic upgrade head でデータベースが構築されること（データ移行・バックフィル系）。

本ファイルは既存データに対する安全性を検証するテスト（CODING_RULES.md「DBマイグレーション
のテスト」）のうち、prompt_template以外のテーブルのデータ移行・バックフィルを対象とする。
`tests/migration_helpers.py`（`upgrade_to`）を使い、`MICHINARI_DATABASE_URL`を一時ファイルへ
切り替えた上で対象マイグレーションの前後を検証する。prompt_templateの初期文面移行は
test_migration_prompt.py、最終スキーマの構造検証はtest_migration_schema.pyを参照
（実装フェーズ分割計画書S02、test_migration.pyからの分割）。
"""

import sqlite3
from datetime import datetime

from tests import migration_helpers


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


def test_slot_allocation_migration_converts_ratio_into_per_slot_minutes(tmp_path, monkeypatch):
    """既存の resource_ratio が「比率 × 各スロットの連続時間（分）」として各スロットへ
    転記され、切り捨てによりスロット容量を超えないこと（Phase28完了条件）。"""
    db_path = tmp_path / "slot_allocation_migration.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("c1a5f9e3d7b2")  # スロット単位化（head）の1つ前

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO resource_slot "
            "(id, name, start_time, end_time, environment, is_active, display_order, "
            "updated_at, created_at) "
            "VALUES (1, '通勤', '07:00:00.000000', '08:00:00.000000', 'MOBILE', 1, 1, "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.execute(
            "INSERT INTO resource_slot "
            "(id, name, start_time, end_time, environment, is_active, display_order, "
            "updated_at, created_at) "
            "VALUES (2, '夜', '20:00:00.000000', '21:30:00.000000', 'PC', 1, 2, "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        # 比率の合計は1.0（旧仕様の上限ちょうど）。
        connection.execute(
            "INSERT INTO goal (id, category, name, start_date, status, resource_ratio, "
            "updated_at, created_at) "
            "VALUES (1, 'EXAM', '簿記2級', '2026-01-01', 'ACTIVE', 0.75, "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.execute(
            "INSERT INTO goal (id, category, name, start_date, status, resource_ratio, "
            "updated_at, created_at) "
            "VALUES (2, 'EXAM', '応用情報', '2026-01-01', 'ACTIVE', 0.25, "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.commit()
    finally:
        connection.close()

    migration_helpers.upgrade_to("head")

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT goal_id, slot_id, minutes FROM goal_slot_allocation ORDER BY slot_id, goal_id"
        ).fetchall()
    finally:
        connection.close()

    # 通勤=60分 → 45分/15分、夜=90分 → 67分（0.75×90=67.5の切り捨て）/22分（22.5の切り捨て）。
    assert rows == [(1, 1, 45), (2, 1, 15), (1, 2, 67), (2, 2, 22)]
    assert 45 + 15 <= 60
    assert 67 + 22 <= 90


def test_slot_allocation_migration_without_slots_keeps_allocation_empty(tmp_path, monkeypatch):
    """スロットが1件も無い状態で移行した場合、転記先が無いため配分は空のまま引き継がれる
    こと（エラーにはしない。実装フェーズ分割計画書Phase28）。"""
    db_path = tmp_path / "slot_allocation_migration_no_slots.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("c1a5f9e3d7b2")  # スロット単位化（head）の1つ前

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO goal (id, category, name, start_date, status, resource_ratio, "
            "updated_at, created_at) "
            "VALUES (1, 'EXAM', 'スロット未設定の目標', '2026-01-01', 'ACTIVE', 0.5, "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.commit()
    finally:
        connection.close()

    migration_helpers.upgrade_to("head")

    connection = sqlite3.connect(db_path)
    try:
        count = connection.execute("SELECT COUNT(*) FROM goal_slot_allocation").fetchone()[0]
        name = connection.execute("SELECT name FROM goal WHERE id = 1").fetchone()[0]
    finally:
        connection.close()

    assert count == 0
    assert name == "スロット未設定の目標"


def test_slot_allocation_migration_preserves_existing_study_log_minutes(tmp_path, monkeypatch):
    """既存の study_log.minutes_spent は「スロット別入力の合計」へ意味が変わるだけで、
    値も内訳の欠如も安全に引き継がれること（実効速度8.1が無改修で動作する前提）。"""
    db_path = tmp_path / "slot_allocation_migration_study_log.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("c1a5f9e3d7b2")  # スロット単位化（head）の1つ前

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO goal (id, category, name, start_date, status, resource_ratio, "
            "updated_at, created_at) "
            "VALUES (1, 'EXAM', '簿記2級', '2026-01-01', 'ACTIVE', 0.5, "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.execute(
            "INSERT INTO material (id, goal_id, name, unit_label, total_amount, "
            "planned_cycles, start_date, due_date, due_date_is_manual, "
            "required_environment, quality_metric_type, is_active, display_order, "
            "updated_at, created_at) "
            "VALUES (1, 1, '過去問集', '問', 100, 1, '2026-01-01', '2026-03-01', 0, 'ANY', "
            "'NONE', 1, 1, '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.execute(
            "INSERT INTO daily_record (id, record_date, created_at) "
            "VALUES (1, '2026-02-01', '2026-02-01T00:00:00')"
        )
        connection.execute(
            "INSERT INTO study_log (id, daily_record_id, material_id, minutes_spent, "
            "amount_completed, cycle_number, created_at) "
            "VALUES (1, 1, 1, 90, 30, 1, '2026-02-01T00:00:00')"
        )
        connection.commit()
    finally:
        connection.close()

    migration_helpers.upgrade_to("head")

    connection = sqlite3.connect(db_path)
    try:
        minutes = connection.execute("SELECT minutes_spent FROM study_log WHERE id = 1").fetchone()[
            0
        ]
        breakdown = connection.execute(
            "SELECT COUNT(*) FROM study_log_slot_time WHERE study_log_id = 1"
        ).fetchone()[0]
    finally:
        connection.close()

    assert minutes == 90
    assert breakdown == 0


def test_reading_page_fields_migration_backfills_total_pages_and_drops_pages_read(
    tmp_path, monkeypatch
):
    """既存データがある状態で a9e3c5b71d64 を適用できること（CODING_RULES.md）。

    総ページ数が未入力だった書籍は、記録済みの現在ページの最大値で補填され、NOT NULL化
    しても行が失われないこと。総ページ数が入力済みの書籍はその値が保持されること。
    """
    db_path = tmp_path / "reading_page_fields_migration.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("f2b7c4a91d3e")  # ページ項目の見直し（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        for goal_id, name in ((1, "読書目標A"), (2, "読書目標B")):
            connection.execute(
                "INSERT INTO goal (id, category, name, start_date, status, "
                "updated_at, created_at) "
                f"VALUES ({goal_id}, 'READING', '{name}', '2026-01-01', 'ACTIVE', "
                "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
            )
        # 総ページ数が未入力の書籍（補填の対象）と、入力済みの書籍（保持されること）。
        connection.execute(
            "INSERT INTO book (id, goal_id, title, total_pages, start_date, due_date, "
            "updated_at, created_at) "
            "VALUES (1, 1, '総ページ数未入力の本', NULL, '2026-01-01', '2026-06-30', "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.execute(
            "INSERT INTO book (id, goal_id, title, total_pages, start_date, due_date, "
            "updated_at, created_at) "
            "VALUES (2, 2, '総ページ数入力済みの本', 400, '2026-01-01', '2026-06-30', "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.execute(
            "INSERT INTO daily_record (id, record_date, created_at) "
            "VALUES (1, '2026-02-01', '2026-02-01T00:00:00')"
        )
        connection.execute(
            "INSERT INTO reading_log (id, daily_record_id, book_id, recall_body, "
            "pages_read, current_page, created_at) "
            "VALUES (1, 1, 1, '想起本文', 20, 120, '2026-02-01T00:00:00')"
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        total_pages = dict(connection.execute("SELECT id, total_pages FROM book").fetchall())
        reading_log_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(reading_log)").fetchall()
        }
        recall_body, current_page = connection.execute(
            "SELECT recall_body, current_page FROM reading_log WHERE id = 1"
        ).fetchone()

    assert total_pages == {1: 120, 2: 400}
    assert "pages_read" not in reading_log_columns
    assert (recall_body, current_page) == ("想起本文", 120)


def test_reading_page_fields_migration_backfills_book_without_reading_log(tmp_path, monkeypatch):
    """現在ページの記録が1件も無い書籍は、補填の根拠が無いため既定値（1）を置くこと。
    NOT NULL化で行が失われないことが目的であり、利用者が書籍編集で訂正する前提。"""
    db_path = tmp_path / "reading_page_fields_migration_no_log.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("f2b7c4a91d3e")  # ページ項目の見直し（head）の1つ前

    with migration_helpers.sqlite_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO goal (id, category, name, start_date, status, updated_at, created_at) "
            "VALUES (1, 'READING', '読書目標A', '2026-01-01', 'ACTIVE', "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
        connection.execute(
            "INSERT INTO book (id, goal_id, title, total_pages, start_date, due_date, "
            "updated_at, created_at) "
            "VALUES (1, 1, '記録の無い本', NULL, '2026-01-01', '2026-06-30', "
            "'2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )

    migration_helpers.upgrade_to("head")

    with migration_helpers.sqlite_connection(db_path) as connection:
        total_pages = connection.execute("SELECT total_pages FROM book WHERE id = 1").fetchone()[0]

    assert total_pages == 1


def test_goal_status_history_migration_restores_known_transitions_from_timestamps(
    tmp_path, monkeypatch
):
    """目標の状態遷移履歴（5e0f3b7c2a91）の初期値が既存の時刻列から復元されること（開発Todo 3-3）。

    既存の目標には遷移の記録が無いため、確実に分かる遷移だけを復元する（作成→開始→現在の状態）。
    再開日（resumed_at）は既存行ではNULLのまま引き継がれる。
    """
    db_path = tmp_path / "goal_status_history_migration.db"
    monkeypatch.setenv("MICHINARI_DATABASE_URL", f"sqlite:///{db_path}")

    migration_helpers.upgrade_to("4d9e2a6b1c7f")  # 状態遷移履歴の追加（head）の1つ前

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        for name, status, activated_at, closed_at in [
            ("下書き", "DRAFT", None, None),
            ("実行中", "ACTIVE", "2026-02-01T00:00:00", None),
            ("一時停止", "PAUSED", "2026-02-01T00:00:00", None),
            ("中断", "CLOSED_WITHOUT_RESULT", "2026-02-01T00:00:00", "2026-03-01T00:00:00"),
        ]:
            cursor.execute(
                "INSERT INTO goal (name, start_date, status, category, activated_at, closed_at, "
                "updated_at, created_at) VALUES (?, '2026-01-01', ?, 'EXAM', ?, ?, "
                "'2026-02-15T00:00:00', '2026-01-10T00:00:00')",
                (name, status, activated_at, closed_at),
            )
        connection.commit()
    finally:
        connection.close()

    migration_helpers.upgrade_to("head")

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT g.name, h.from_status, h.to_status, h.changed_at "
            "FROM goal_status_history h JOIN goal g ON g.id = h.goal_id "
            "ORDER BY g.id, h.id"
        ).fetchall()
        resumed = connection.execute("SELECT resumed_at FROM goal").fetchall()
    finally:
        connection.close()

    by_goal: dict[str, list[tuple]] = {}
    for name, from_status, to_status, changed_at in rows:
        by_goal.setdefault(name, []).append(
            (from_status, to_status, datetime.fromisoformat(changed_at))
        )
    assert by_goal["下書き"] == [(None, "DRAFT", datetime(2026, 1, 10))]
    assert by_goal["実行中"] == [
        (None, "DRAFT", datetime(2026, 1, 10)),
        ("DRAFT", "ACTIVE", datetime(2026, 2, 1)),
    ]
    assert by_goal["一時停止"][-1] == ("ACTIVE", "PAUSED", datetime(2026, 2, 15))
    assert by_goal["中断"][-1] == ("ACTIVE", "CLOSED_WITHOUT_RESULT", datetime(2026, 3, 1))
    assert all(row[0] is None for row in resumed)
