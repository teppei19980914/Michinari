"""export_service_exam のテスト（設計書データ構造編7章、仕様書6.10 SC-13、
実装フェーズ分割計画書Phase10・S02）。共通のファイル出力機構のテストは
test_export_service_common.pyを参照（実装フェーズ分割計画書S02、test_export_service.py
からの分割）。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.constants.enums import (
    Environment,
    ExamResultType,
    GoalStatus,
    PassingScoreType,
    QualityMetricType,
)
from app.models.goal import ExamSubject, Goal
from app.models.material import Material
from app.models.record import (
    ChatMessage,
    DailyGoalDiary,
    DailyRecord,
    ExamResult,
    StudyLog,
    StudyLogSlotTime,
    WeeklySummary,
)
from app.models.resource import ResourceSlot
from app.services import export_progress, export_service_common
from app.services.export_service_common import ExportSelection


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _make_goal(session, name="目標A"):
    goal = Goal(
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_subject(
    session,
    goal,
    name="科目A",
    passing_score=60.0,
    passing_score_type=PassingScoreType.PERCENTAGE,
    passing_score_max=None,
):
    subject = ExamSubject(
        goal_id=goal.id,
        name=name,
        exam_date_type="FIXED",
        exam_date_fixed=dt.date(2026, 6, 1),
        passing_score=passing_score,
        passing_score_type=passing_score_type,
        passing_score_max=passing_score_max,
        display_order=1,
    )
    session.add(subject)
    session.flush()
    return subject


def _make_material(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        name="教材A",
        unit_label="ページ",
        total_amount=100.0,
        planned_cycles=1,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 5, 31),
        quality_metric_type=QualityMetricType.OBJECTIVE,
        display_order=1,
    )
    defaults.update(overrides)
    material = Material(**defaults)
    session.add(material)
    session.flush()
    return material


def _add_study_log(session, material, record_date, **overrides):
    record = session.query(DailyRecord).filter_by(record_date=record_date).first()
    if record is None:
        record = DailyRecord(record_date=record_date, exam_record_state="REPORTED")
        session.add(record)
        session.flush()
        session.add(
            DailyGoalDiary(
                daily_record_id=record.id,
                goal_id=material.goal_id,
                diary_body="今日の所感",
                diary_learned="学んだこと",
            )
        )
    defaults = dict(
        daily_record_id=record.id,
        material_id=material.id,
        minutes_spent=30,
        amount_completed=10.0,
        cycle_number=1,
        quality_value=80.0,
    )
    defaults.update(overrides)
    session.add(StudyLog(**defaults))
    session.add(
        ChatMessage(
            daily_record_id=record.id,
            goal_id=material.goal_id,
            purpose="DAILY_FEEDBACK",
            role="USER",
            content="今日は順調です",
            sequence=1,
        )
    )
    session.flush()
    return record


def _stub_send_message(monkeypatch, *, response="生成結果"):
    def _fake(session, *, chat_uid, message):
        return ai_client.SendResult(response_text=response, latency_ms=5)

    monkeypatch.setattr(ai_client, "send_message", _fake)
    counter = iter(range(1000))
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: f"chat-{next(counter)}",
    )


# --- build_export_data ---


def test_build_export_data_includes_all_selected_sections_by_default(seeded_session):
    goal = _make_goal(seeded_session)
    subject = _make_subject(seeded_session, goal)
    material = _make_material(seeded_session, goal)
    _add_study_log(seeded_session, material, dt.date(2026, 2, 1))
    seeded_session.add(
        ExamResult(
            subject_id=subject.id, taken_date=dt.date(2026, 6, 1), result=ExamResultType.PASS
        )
    )
    seeded_session.add(
        WeeklySummary(
            goal_id=goal.id,
            week_start_date=dt.date(2026, 1, 26),
            week_end_date=dt.date(2026, 2, 1),
            summary_body="週の要約",
        )
    )
    seeded_session.flush()

    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["schema_version"] == export_service_common.SCHEMA_VERSION
    assert data["anonymized"] is False
    assert data["goal"]["name"] == "目標A"
    assert data["subjects"][0]["name"] == "科目A"
    assert data["materials"][0]["name"] == "教材A"
    assert data["summary"]["total_minutes"] == 30
    assert data["daily_records"][0]["amount"] == 10.0
    assert data["quality_trend"][0]["material"] == "教材A"
    assert data["weekly_summaries"][0]["body"] == "週の要約"
    assert data["results"][0]["result"] == "PASS"
    assert data["retrospective"] is None
    # 既定選択では日記本文・AI対話履歴は含まれない（仕様書6.10）。
    assert "diaries" not in data
    assert "ai_dialogue" not in data


def test_build_diaries_and_dialogue_return_empty_for_goal_without_materials(seeded_session):
    goal = _make_goal(seeded_session)

    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(diary=True, ai_dialogue=True),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["diaries"] == []
    assert data["ai_dialogue"] == []


def test_build_dialogue_returns_empty_when_materials_exist_but_no_study_logs(seeded_session):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)

    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(ai_dialogue=True),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["ai_dialogue"] == []


def test_build_export_data_includes_diary_and_dialogue_when_selected(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _add_study_log(seeded_session, material, dt.date(2026, 2, 1))

    selection = ExportSelection(diary=True, ai_dialogue=True)
    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["diaries"][0]["body"] == "今日の所感"
    assert data["ai_dialogue"][0]["content"] == "今日は順調です"


def test_build_ai_dialogue_excludes_other_goals_messages_on_same_date(seeded_session):
    """複数目標が同時進行していた日に、他目標(他カテゴリを含む)のAI対話が混入しないこと。

    Phase26でchat_message.goal_idを追加する前は、対象goalのstudy_logがある日付に
    絞り込んだ上でその日のchat_messageを無条件に取得していたため、同日に他の目標の
    日次フィードバック対話があると誤って混入していた（横展開チェックで発見した既存バグ）。
    """
    goal_a = _make_goal(seeded_session, name="目標A")
    goal_b = _make_goal(seeded_session, name="目標B")
    material_a = _make_material(seeded_session, goal_a)
    material_b = _make_material(seeded_session, goal_b, name="教材B")
    record = DailyRecord(record_date=dt.date(2026, 2, 1), exam_record_state="REPORTED")
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add_all(
        [
            StudyLog(
                daily_record_id=record.id,
                material_id=material_a.id,
                minutes_spent=30,
                amount_completed=10.0,
                cycle_number=1,
                quality_value=80.0,
            ),
            StudyLog(
                daily_record_id=record.id,
                material_id=material_b.id,
                minutes_spent=30,
                amount_completed=10.0,
                cycle_number=1,
                quality_value=80.0,
            ),
            ChatMessage(
                daily_record_id=record.id,
                goal_id=goal_a.id,
                purpose="DAILY_FEEDBACK",
                role="ASSISTANT",
                content="Aへの応答",
                sequence=1,
            ),
            ChatMessage(
                daily_record_id=record.id,
                goal_id=goal_b.id,
                purpose="DAILY_FEEDBACK",
                role="ASSISTANT",
                content="Bへの応答",
                sequence=2,
            ),
        ]
    )
    seeded_session.flush()

    data = export_service_common.build_export_data(
        seeded_session,
        goal_a,
        ExportSelection(ai_dialogue=True),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    contents = [entry["content"] for entry in data["ai_dialogue"]]
    assert contents == ["Aへの応答"]


def test_build_ai_dialogue_excludes_unassigned_legacy_messages(seeded_session):
    """目標単位分離より前のレガシーメッセージ(goal_id=NULL)は、どの目標宛てか判別
    不能なため対象に含めないこと(分析タブで手動割り当てすれば対象に含まれる)。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    record = DailyRecord(record_date=dt.date(2026, 2, 1), exam_record_state="REPORTED")
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add_all(
        [
            StudyLog(
                daily_record_id=record.id,
                material_id=material.id,
                minutes_spent=30,
                amount_completed=10.0,
                cycle_number=1,
                quality_value=80.0,
            ),
            ChatMessage(
                daily_record_id=record.id,
                purpose="DAILY_FEEDBACK",
                role="ASSISTANT",
                content="移行前の応答",
                sequence=1,
            ),
        ]
    )
    seeded_session.flush()

    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(ai_dialogue=True),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["ai_dialogue"] == []


def test_build_diaries_excludes_other_goals_diary_on_same_date(seeded_session):
    """複数目標が同時進行していた日に他目標の日記が混入しないこと（L-04関連）。"""
    goal_a = _make_goal(seeded_session, name="目標A")
    goal_b = _make_goal(seeded_session, name="目標B")
    material_a = _make_material(seeded_session, goal_a)
    material_b = _make_material(seeded_session, goal_b, name="教材B")
    record = DailyRecord(record_date=dt.date(2026, 2, 1), exam_record_state="REPORTED")
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add_all(
        [
            DailyGoalDiary(
                daily_record_id=record.id,
                goal_id=goal_a.id,
                diary_body="Aの日記",
                diary_learned="Aで学んだこと",
            ),
            DailyGoalDiary(
                daily_record_id=record.id,
                goal_id=goal_b.id,
                diary_body="Bの日記",
                diary_learned="Bで学んだこと",
            ),
            StudyLog(
                daily_record_id=record.id,
                material_id=material_a.id,
                minutes_spent=30,
                amount_completed=10.0,
                cycle_number=1,
                quality_value=80.0,
            ),
            StudyLog(
                daily_record_id=record.id,
                material_id=material_b.id,
                minutes_spent=30,
                amount_completed=10.0,
                cycle_number=1,
                quality_value=80.0,
            ),
        ]
    )
    seeded_session.flush()

    data_a = export_service_common.build_export_data(
        seeded_session,
        goal_a,
        ExportSelection(diary=True),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    data_b = export_service_common.build_export_data(
        seeded_session,
        goal_b,
        ExportSelection(diary=True),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert [d["body"] for d in data_a["diaries"]] == ["Aの日記"]
    assert [d["body"] for d in data_b["diaries"]] == ["Bの日記"]


def test_build_export_data_excludes_diary_when_anonymized_even_if_selected(seeded_session):
    """仕様書6.10匿名化オプション「日記本文: 全面的に除外」（選択有無に関わらず）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _add_study_log(seeded_session, material, dt.date(2026, 2, 1))

    selection = ExportSelection(diary=True)
    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=True,
    )

    assert "diaries" not in data


def test_build_export_data_excludes_ai_dialogue_when_anonymized_even_if_selected(seeded_session):
    """実装フェーズ分割計画書Phase10完了条件「匿名化時に日記本文とAI対話履歴が
    除外される」（選択有無に関わらず）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _add_study_log(seeded_session, material, dt.date(2026, 2, 1))

    selection = ExportSelection(ai_dialogue=True)
    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=True,
    )

    assert "ai_dialogue" not in data


def test_build_export_data_weekly_summaries_uses_anonymized_flag(seeded_session):
    goal = _make_goal(seeded_session)
    seeded_session.add(
        WeeklySummary(
            goal_id=goal.id,
            week_start_date=dt.date(2026, 1, 26),
            week_end_date=dt.date(2026, 2, 1),
            summary_body="通常版",
            is_anonymized=False,
        )
    )
    seeded_session.add(
        WeeklySummary(
            goal_id=goal.id,
            week_start_date=dt.date(2026, 1, 26),
            week_end_date=dt.date(2026, 2, 1),
            summary_body="匿名化版",
            is_anonymized=True,
        )
    )
    seeded_session.flush()

    normal = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    anonymized = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=True,
    )

    assert normal["weekly_summaries"][0]["body"] == "通常版"
    assert anonymized["weekly_summaries"][0]["body"] == "匿名化版"


# --- render_markdown ---


def test_render_markdown_includes_headings_for_selected_sections(seeded_session):
    goal = _make_goal(seeded_session)
    _make_subject(seeded_session, goal)
    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    markdown = export_service_common.render_markdown(data, ExportSelection())

    assert "# 目標A" in markdown
    assert "## 1. 概要" in markdown
    assert "## 3. 学習量" in markdown
    assert "## 4. 教材構成" in markdown
    assert "合格基準: 60%" in markdown


def test_render_markdown_formats_raw_score_passing_score(seeded_session):
    goal = _make_goal(seeded_session)
    _make_subject(
        seeded_session,
        goal,
        passing_score=700.0,
        passing_score_type=PassingScoreType.RAW_SCORE,
        passing_score_max=1000.0,
    )
    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    markdown = export_service_common.render_markdown(data, ExportSelection())

    assert "合格基準: 700/1000点" in markdown


def test_render_markdown_formats_unset_passing_score(seeded_session):
    goal = _make_goal(seeded_session)
    _make_subject(seeded_session, goal, passing_score=None)
    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    markdown = export_service_common.render_markdown(data, ExportSelection())

    assert "合格基準: 未設定" in markdown


def test_render_markdown_omits_headings_for_unselected_sections(seeded_session):
    goal = _make_goal(seeded_session)
    selection = ExportSelection(
        goal_overview=False,
        materials=False,
        summary=False,
        daily_records=False,
        quality_trend=False,
        replan_history=False,
        weekly_summaries=False,
        recap_themes=False,
        exam_results=False,
        retrospective=False,
    )
    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    markdown = export_service_common.render_markdown(data, selection)

    assert "## 1. 概要" not in markdown
    assert "## 3. 学習量" not in markdown
    assert "## 9. 受験結果" not in markdown


def test_render_markdown_includes_diary_and_dialogue_sections_when_present(seeded_session):
    goal = _make_goal(seeded_session)
    subject = _make_subject(seeded_session, goal)
    material = _make_material(seeded_session, goal)
    _add_study_log(seeded_session, material, dt.date(2026, 2, 1))
    seeded_session.add(
        ExamResult(
            subject_id=subject.id, taken_date=dt.date(2026, 6, 1), result=ExamResultType.PASS
        )
    )
    seeded_session.flush()
    selection = ExportSelection(diary=True, ai_dialogue=True)
    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    markdown = export_service_common.render_markdown(data, selection)

    assert "## 9. 受験結果" in markdown
    assert "## 10. 日記" in markdown
    assert "今日の所感" in markdown
    assert "## 11. AI対話履歴" in markdown
    assert "今日は順調です" in markdown


# --- execute_export ---


def test_execute_export_with_anonymize_regenerates_weekly_summaries_and_retrospective(
    seeded_session, monkeypatch, tmp_path
):
    monkeypatch.setattr(export_service_common, "EXPORT_DIR", tmp_path)
    goal = _make_goal(seeded_session)
    goal.status = GoalStatus.CLOSED_WITH_RESULT  # 総括レポートは完了した目標のみ持つ
    material = _make_material(seeded_session, goal)
    _add_study_log(seeded_session, material, dt.date(2026, 1, 27))  # 火曜、週2026-01-26開始
    seeded_session.add(
        WeeklySummary(
            goal_id=goal.id,
            week_start_date=dt.date(2026, 1, 26),
            week_end_date=dt.date(2026, 2, 1),
            summary_body="元の週次要約",
        )
    )
    seeded_session.commit()
    _stub_send_message(monkeypatch, response="匿名化された内容")

    content = export_service_common.execute_export(
        seeded_session, goal, ExportSelection(), anonymize=True
    )

    assert content.data["anonymized"] is True
    assert content.data["weekly_summaries"][0]["body"] == "匿名化された内容"
    assert content.data["retrospective"] == "匿名化された内容"
    anonymized_rows = (
        seeded_session.query(WeeklySummary).filter(WeeklySummary.is_anonymized.is_(True)).all()
    )
    assert len(anonymized_rows) == 1
    # 元の週次要約は削除されず残っている（データ構造編7.3）。
    original_rows = (
        seeded_session.query(WeeklySummary).filter(WeeklySummary.is_anonymized.is_(False)).all()
    )
    assert len(original_rows) == 1
    assert original_rows[0].summary_body == "元の週次要約"
    # 完了後は進捗が後始末される（Phase10注意点「進捗を表示すること」、export_progress）。
    assert export_progress.get(goal.id) is None


def test_execute_export_with_anonymize_does_not_generate_retrospective_for_active_goal(
    seeded_session, monkeypatch, tmp_path
):
    """実行中の資格目標を匿名化エクスポートしても、総括レポートを（AIで）生成しないこと。
    総括レポートは完了した目標のみ持ち、生成は出力画面の生成ボタンでのみ行う（利用者方針2026-10-04）。"""
    from app.models.retrospective import GoalRetrospective

    monkeypatch.setattr(export_service_common, "EXPORT_DIR", tmp_path)
    goal = _make_goal(seeded_session)  # 実行中（ACTIVE）のまま
    material = _make_material(seeded_session, goal)
    _add_study_log(seeded_session, material, dt.date(2026, 1, 27))
    seeded_session.commit()
    _stub_send_message(monkeypatch, response="生成されてはいけない")

    content = export_service_common.execute_export(
        seeded_session, goal, ExportSelection(), anonymize=True
    )

    assert content.data["anonymized"] is True
    assert content.data["retrospective"] is None
    assert seeded_session.query(GoalRetrospective).filter_by(goal_id=goal.id).count() == 0


def test_execute_export_with_anonymize_records_progress_while_running(
    seeded_session, monkeypatch, tmp_path
):
    """匿名化実行中、週次要約1件ごとの生成完了に合わせて進捗が更新されることを確認する
    （実装フェーズ分割計画書Phase10注意点「進捗を表示すること」）。"""
    monkeypatch.setattr(export_service_common, "EXPORT_DIR", tmp_path)
    goal = _make_goal(seeded_session)
    goal.status = GoalStatus.CLOSED_WITH_RESULT
    material = _make_material(seeded_session, goal)
    _add_study_log(seeded_session, material, dt.date(2026, 1, 27))
    seeded_session.add(
        WeeklySummary(
            goal_id=goal.id,
            week_start_date=dt.date(2026, 1, 26),
            week_end_date=dt.date(2026, 2, 1),
            summary_body="元の週次要約",
        )
    )
    seeded_session.commit()
    _stub_send_message(monkeypatch, response="匿名化された内容")

    observed: list[export_progress.ExportProgress | None] = []
    original_advance = export_progress.advance

    def _spy_advance(goal_id: int) -> None:
        original_advance(goal_id)
        observed.append(export_progress.get(goal_id))

    monkeypatch.setattr(export_progress, "advance", _spy_advance)

    export_service_common.execute_export(seeded_session, goal, ExportSelection(), anonymize=True)

    # 週次要約1件＋総括レポート1件 = 合計2ステップ。完了ごとにcompletedが進む。
    assert [p.completed for p in observed] == [1, 2]
    assert all(p.total == 2 for p in observed)


def test_build_export_data_includes_slot_minutes_breakdown(seeded_session):
    """実績推移に投下時間の時間枠別内訳が含まれること（データ構造編7.1、schema_version 1.1）。

    時間枠が記録後に削除された内訳は名称を持たないため slot=None として出力される
    （study_log_slot_time.slot_id は ON DELETE SET NULL）。
    """
    goal = _make_goal(seeded_session)
    _make_subject(seeded_session, goal)
    material = _make_material(seeded_session, goal)
    _add_study_log(seeded_session, material, dt.date(2026, 1, 5))
    study_log = seeded_session.query(StudyLog).filter_by(material_id=material.id).one()
    slot = ResourceSlot(
        name="夜",
        start_time=dt.time(20, 0),
        end_time=dt.time(22, 0),
        environment=Environment.PC,
        display_order=1,
    )
    seeded_session.add(slot)
    seeded_session.flush()
    seeded_session.add(StudyLogSlotTime(study_log_id=study_log.id, slot_id=slot.id, minutes=20))
    seeded_session.add(StudyLogSlotTime(study_log_id=study_log.id, slot_id=None, minutes=10))
    seeded_session.flush()

    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    record = next(r for r in data["daily_records"] if r["date"] == "2026-01-05")
    assert record["slot_minutes"] == [
        {"slot": "夜", "minutes": 20},
        {"slot": None, "minutes": 10},
    ]
