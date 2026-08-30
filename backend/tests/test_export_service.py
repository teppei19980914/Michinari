"""export_service のテスト（設計書データ構造編7章、仕様書6.10 SC-13、
実装フェーズ分割計画書Phase10）。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.constants.enums import ExamResultType, GoalStatus, PassingScoreType, QualityMetricType
from app.models.goal import ExamSubject, Goal
from app.models.material import Material
from app.models.record import (
    ChatMessage,
    DailyGoalDiary,
    DailyRecord,
    ExamResult,
    StudyLog,
    WeeklySummary,
)
from app.services import export_progress, export_service


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _make_goal(session, name="目標A"):
    goal = Goal(
        name=name, start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE, resource_ratio=1.0
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
        record = DailyRecord(record_date=record_date, record_state="REPORTED")
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
        ChatMessage(daily_record_id=record.id, role="USER", content="今日は順調です", sequence=1)
    )
    session.flush()
    return record


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

    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["schema_version"] == "1.0"
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


def test_build_export_data_omits_unselected_sections(seeded_session):
    goal = _make_goal(seeded_session)
    _make_subject(seeded_session, goal)
    material = _make_material(seeded_session, goal)
    _add_study_log(seeded_session, material, dt.date(2026, 2, 1))

    selection = export_service.ExportSelection(
        goal_overview=False,
        materials=False,
        summary=False,
        daily_records=False,
        quality_trend=False,
        replan_history=False,
        weekly_summaries=False,
        exam_results=False,
        retrospective=False,
    )
    data = export_service.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert set(data.keys()) == {"schema_version", "exported_at", "anonymized"}


def test_build_diaries_and_dialogue_return_empty_for_goal_without_materials(seeded_session):
    goal = _make_goal(seeded_session)

    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(diary=True, ai_dialogue=True),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["diaries"] == []
    assert data["ai_dialogue"] == []


def test_build_dialogue_returns_empty_when_materials_exist_but_no_study_logs(seeded_session):
    goal = _make_goal(seeded_session)
    _make_material(seeded_session, goal)

    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(ai_dialogue=True),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["ai_dialogue"] == []


def test_build_export_data_includes_diary_and_dialogue_when_selected(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _add_study_log(seeded_session, material, dt.date(2026, 2, 1))

    selection = export_service.ExportSelection(diary=True, ai_dialogue=True)
    data = export_service.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["diaries"][0]["body"] == "今日の所感"
    assert data["ai_dialogue"][0]["content"] == "今日は順調です"


def test_build_export_data_excludes_diary_when_anonymized_even_if_selected(seeded_session):
    """仕様書6.10匿名化オプション「日記本文: 全面的に除外」（選択有無に関わらず）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _add_study_log(seeded_session, material, dt.date(2026, 2, 1))

    selection = export_service.ExportSelection(diary=True)
    data = export_service.build_export_data(
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

    selection = export_service.ExportSelection(ai_dialogue=True)
    data = export_service.build_export_data(
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

    normal = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    anonymized = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(),
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
    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    markdown = export_service.render_markdown(data, export_service.ExportSelection())

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
    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    markdown = export_service.render_markdown(data, export_service.ExportSelection())

    assert "合格基準: 700/1000点" in markdown


def test_render_markdown_formats_unset_passing_score(seeded_session):
    goal = _make_goal(seeded_session)
    _make_subject(seeded_session, goal, passing_score=None)
    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    markdown = export_service.render_markdown(data, export_service.ExportSelection())

    assert "合格基準: 未設定" in markdown


def test_render_markdown_omits_headings_for_unselected_sections(seeded_session):
    goal = _make_goal(seeded_session)
    selection = export_service.ExportSelection(
        goal_overview=False,
        materials=False,
        summary=False,
        daily_records=False,
        quality_trend=False,
        replan_history=False,
        weekly_summaries=False,
        exam_results=False,
        retrospective=False,
    )
    data = export_service.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    markdown = export_service.render_markdown(data, selection)

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
    selection = export_service.ExportSelection(diary=True, ai_dialogue=True)
    data = export_service.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    markdown = export_service.render_markdown(data, selection)

    assert "## 9. 受験結果" in markdown
    assert "## 10. 日記" in markdown
    assert "今日の所感" in markdown
    assert "## 11. AI対話履歴" in markdown
    assert "今日は順調です" in markdown


# --- execute_export ---


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


def test_execute_export_writes_markdown_and_json_files(seeded_session, monkeypatch, tmp_path):
    monkeypatch.setattr(export_service, "EXPORT_DIR", tmp_path)
    goal = _make_goal(seeded_session)

    content = export_service.execute_export(
        seeded_session, goal, export_service.ExportSelection(), anonymize=False
    )

    assert content.markdown_path.exists()
    assert content.json_path.exists()
    assert content.markdown_path.read_text(encoding="utf-8") == content.markdown


def test_execute_export_with_anonymize_regenerates_weekly_summaries_and_retrospective(
    seeded_session, monkeypatch, tmp_path
):
    monkeypatch.setattr(export_service, "EXPORT_DIR", tmp_path)
    goal = _make_goal(seeded_session)
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

    content = export_service.execute_export(
        seeded_session, goal, export_service.ExportSelection(), anonymize=True
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


def test_execute_export_with_anonymize_records_progress_while_running(
    seeded_session, monkeypatch, tmp_path
):
    """匿名化実行中、週次要約1件ごとの生成完了に合わせて進捗が更新されることを確認する
    （実装フェーズ分割計画書Phase10注意点「進捗を表示すること」）。"""
    monkeypatch.setattr(export_service, "EXPORT_DIR", tmp_path)
    goal = _make_goal(seeded_session)
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

    export_service.execute_export(
        seeded_session, goal, export_service.ExportSelection(), anonymize=True
    )

    # 週次要約1件＋総括レポート1件 = 合計2ステップ。完了ごとにcompletedが進む。
    assert [p.completed for p in observed] == [1, 2]
    assert all(p.total == 2 for p in observed)
