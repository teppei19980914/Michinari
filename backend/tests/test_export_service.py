"""export_service のテスト（設計書データ構造編7章、仕様書6.10 SC-13、
実装フェーズ分割計画書Phase10）。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.constants.enums import (
    ExamResultType,
    GoalCategory,
    GoalStatus,
    PassingScoreType,
    QualityMetricType,
)
from app.models.book import Book
from app.models.goal import ExamSubject, Goal
from app.models.material import Material
from app.models.record import (
    ChatMessage,
    DailyGoalDiary,
    DailyRecord,
    ExamResult,
    ReadingLog,
    StudyLog,
    WeeklySummary,
    WorkLog,
)
from app.models.work import WorkAssignment
from app.services import export_progress, export_service


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _make_goal(session, name="目標A"):
    goal = Goal(
        name=name, start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE, )
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


def _make_reading_goal(session, name="読書目標A"):
    goal = Goal(
        name=name,
        category=GoalCategory.READING,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_book(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        title="書籍A",
        author="著者A",
        total_pages=300,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 3, 1),
    )
    defaults.update(overrides)
    book = Book(**defaults)
    session.add(book)
    session.flush()
    return book


def _add_reading_log(session, book, record_date, **overrides):
    record = session.query(DailyRecord).filter_by(record_date=record_date).first()
    if record is None:
        record = DailyRecord(record_date=record_date, reading_record_state="REPORTED")
        session.add(record)
        session.flush()
    defaults = dict(
        daily_record_id=record.id,
        book_id=book.id,
        recall_body="今日読んだ内容の想起",
        pages_read=10,
        current_page=50,
    )
    defaults.update(overrides)
    session.add(ReadingLog(**defaults))
    session.flush()
    return record


def _make_work_goal(session, name="仕事目標A"):
    goal = Goal(
        name=name,
        category=GoalCategory.WORK,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_work_assignment(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        client_name="A社",
        expected_content="想定業務内容",
        start_date=dt.date(2026, 1, 1),
    )
    defaults.update(overrides)
    work_assignment = WorkAssignment(**defaults)
    session.add(work_assignment)
    session.flush()
    return work_assignment


def _add_work_log(session, work_assignment, record_date, **overrides):
    record = session.query(DailyRecord).filter_by(record_date=record_date).first()
    if record is None:
        record = DailyRecord(record_date=record_date, work_record_state="REPORTED")
        session.add(record)
        session.flush()
    defaults = dict(
        daily_record_id=record.id, work_assignment_id=work_assignment.id, body="今日の業務内容"
    )
    defaults.update(overrides)
    session.add(WorkLog(**defaults))
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

    data = export_service.build_export_data(
        seeded_session,
        goal_a,
        export_service.ExportSelection(ai_dialogue=True),
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

    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(ai_dialogue=True),
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

    data_a = export_service.build_export_data(
        seeded_session,
        goal_a,
        export_service.ExportSelection(diary=True),
        today=dt.date(2026, 2, 2),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    data_b = export_service.build_export_data(
        seeded_session,
        goal_b,
        export_service.ExportSelection(diary=True),
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


# --- build_export_data（読書目標） ---


def test_build_export_data_for_reading_goal_uses_book_and_reading_summary(seeded_session):
    """読書目標では教材構成・品質指標推移・受験結果・週次要約・リプラン履歴を持たず、
    かわりにbook・読書サマリ（record_days・max_streak_days）を出力する
    （仕様書6.10、設計書データ構造編7.1「読書目標の場合」）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    _add_reading_log(seeded_session, book, dt.date(2026, 1, 1))
    _add_reading_log(seeded_session, book, dt.date(2026, 1, 2))
    _add_reading_log(seeded_session, book, dt.date(2026, 1, 4))

    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(),
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["book"]["title"] == "書籍A"
    assert data["summary"] == {"record_days": 3, "max_streak_days": 2}
    assert [r["date"] for r in data["daily_records"]] == [
        "2026-01-01",
        "2026-01-02",
        "2026-01-04",
    ]
    assert data["daily_records"][0]["recall"] == "今日読んだ内容の想起"
    assert data["retrospective"] is None
    for key in (
        "subjects",
        "materials",
        "quality_trend",
        "replan_history",
        "weekly_summaries",
        "results",
        "diaries",
        "ai_dialogue",
    ):
        assert key not in data


def test_build_export_data_for_reading_goal_excludes_daily_records_when_anonymized(
    seeded_session,
):
    """匿名化時は想起記録（日記相当）を選択有無に関わらず除外する
    （データ構造編7.3、仕様書6.10「読書目標の場合」）。"""
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    _add_reading_log(seeded_session, book, dt.date(2026, 1, 1))

    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(daily_records=True),
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=True,
    )

    assert "daily_records" not in data


def test_build_export_data_for_reading_goal_with_no_reading_logs(seeded_session):
    goal = _make_reading_goal(seeded_session)
    _make_book(seeded_session, goal)

    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(),
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["summary"] == {"record_days": 0, "max_streak_days": 0}
    assert data["daily_records"] == []


def test_build_export_data_for_reading_goal_omits_unselected_sections(seeded_session):
    goal = _make_reading_goal(seeded_session)
    _make_book(seeded_session, goal)

    selection = export_service.ExportSelection(
        goal_overview=False, summary=False, daily_records=False, retrospective=False
    )
    data = export_service.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert set(data.keys()) == {"schema_version", "exported_at", "anonymized"}


# --- render_markdown（読書目標） ---


def test_render_markdown_for_reading_goal_includes_reading_headings(seeded_session):
    goal = _make_reading_goal(seeded_session)
    book = _make_book(seeded_session, goal)
    _add_reading_log(seeded_session, book, dt.date(2026, 1, 1))

    selection = export_service.ExportSelection()
    data = export_service.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    markdown = export_service.render_markdown(data, selection, GoalCategory.READING)

    assert "# 書籍A" in markdown
    assert "## 1. 概要" in markdown
    assert "書名: 書籍A" in markdown
    assert "## 2. 読了レポート" in markdown
    assert "（読了レポートは未生成です）" in markdown
    assert "## 3. 記録量" in markdown
    assert "記録日数: 1日" in markdown
    assert "## 4. 付録：日別の想起記録" in markdown
    assert "今日読んだ内容の想起" in markdown
    # 資格試験向けの見出しは出力しない
    assert "## 4. 教材構成" not in markdown
    assert "## 9. 受験結果" not in markdown


def test_render_markdown_for_reading_goal_omits_headings_for_unselected_sections(seeded_session):
    goal = _make_reading_goal(seeded_session)
    _make_book(seeded_session, goal)

    selection = export_service.ExportSelection(
        goal_overview=False, summary=False, daily_records=False, retrospective=False
    )
    data = export_service.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    markdown = export_service.render_markdown(data, selection, GoalCategory.READING)

    assert "## 1. 概要" not in markdown
    assert "## 2. 読了レポート" not in markdown
    assert "## 3. 記録量" not in markdown
    assert "## 4. 付録：日別の想起記録" not in markdown


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


# --- build_export_data（仕事目標） ---


def test_build_export_data_for_work_goal_uses_work_assignment_and_work_summary(seeded_session):
    """仕事目標では教材構成・品質指標推移・受験結果・週次要約・リプラン履歴を持たず、
    かわりにwork_assignment・仕事サマリ（record_days・max_streak_days）を出力する
    （仕様書6.10、設計書データ構造編7.1「仕事目標の場合」）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment, dt.date(2026, 1, 1))
    _add_work_log(seeded_session, work_assignment, dt.date(2026, 1, 2))
    _add_work_log(seeded_session, work_assignment, dt.date(2026, 1, 4))

    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(),
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["work_assignment"]["name"] == "仕事目標A"
    assert data["work_assignment"]["client_name"] == "A社"
    assert data["summary"] == {"record_days": 3, "max_streak_days": 2}
    assert [r["date"] for r in data["daily_records"]] == [
        "2026-01-01",
        "2026-01-02",
        "2026-01-04",
    ]
    assert data["daily_records"][0]["body"] == "今日の業務内容"
    assert data["retrospectives"] == []
    for key in (
        "subjects",
        "materials",
        "quality_trend",
        "replan_history",
        "weekly_summaries",
        "results",
        "diaries",
        "ai_dialogue",
    ):
        assert key not in data


def test_build_export_data_for_work_goal_excludes_daily_records_when_anonymized(seeded_session):
    """匿名化時は業務記録（日記相当）を選択有無に関わらず除外する
    （データ構造編7.3、仕様書6.10「仕事目標の場合」）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment, dt.date(2026, 1, 1))

    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(daily_records=True),
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=True,
    )

    assert "daily_records" not in data


def test_build_export_data_for_work_goal_lists_retrospectives_newest_first(
    seeded_session, monkeypatch
):
    """対象goalに紐づく全goal_retrospective（period_type問わず）を期間の新しい順に
    列挙する（要件定義書R-80・R-81）。"""
    from app.services import work_report_service

    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch, response="生成結果")
    work_report_service.generate_monthly_report(
        seeded_session, goal, period_key="2026-01", today=dt.date(2026, 2, 1)
    )
    work_report_service.generate_monthly_report(
        seeded_session, goal, period_key="2026-02", today=dt.date(2026, 3, 1)
    )

    data = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(),
        today=dt.date(2026, 3, 1),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert [r["period_key"] for r in data["retrospectives"]] == ["2026-02", "2026-01"]
    assert data["retrospectives"][0]["period_type"] == "MONTHLY"


def test_build_export_data_for_work_goal_omits_unselected_sections(seeded_session):
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)

    selection = export_service.ExportSelection(
        goal_overview=False, summary=False, daily_records=False, retrospective=False
    )
    data = export_service.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert set(data.keys()) == {"schema_version", "exported_at", "anonymized"}


# --- render_markdown（仕事目標） ---


def test_render_markdown_for_work_goal_includes_work_headings(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment, dt.date(2026, 1, 1))

    selection = export_service.ExportSelection()
    data = export_service.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    markdown = export_service.render_markdown(data, selection, GoalCategory.WORK)

    assert "# 仕事目標A" in markdown
    assert "## 1. 概要" in markdown
    assert "案件名: 仕事目標A" in markdown
    assert "取引先・案件の呼称: A社" in markdown
    assert "想定業務内容" in markdown
    assert "## 2. 月次報告・半期評価" in markdown
    assert "（月次報告・半期評価は未生成です）" in markdown
    assert "## 3. 記録量" in markdown
    assert "記録日数: 1日" in markdown
    assert "## 4. 付録：日別の業務記録" in markdown
    assert "今日の業務内容" in markdown
    # 資格試験向けの見出しは出力しない
    assert "## 4. 教材構成" not in markdown
    assert "## 9. 受験結果" not in markdown


def test_render_markdown_for_work_goal_omits_headings_for_unselected_sections(seeded_session):
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)

    selection = export_service.ExportSelection(
        goal_overview=False, summary=False, daily_records=False, retrospective=False
    )
    data = export_service.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    markdown = export_service.render_markdown(data, selection, GoalCategory.WORK)

    assert "## 1. 概要" not in markdown
    assert "## 2. 月次報告・半期評価" not in markdown
    assert "## 3. 記録量" not in markdown
    assert "## 4. 付録：日別の業務記録" not in markdown


# --- execute_export（仕事目標の匿名化） ---


def test_execute_export_anonymized_regenerates_all_work_retrospectives(
    seeded_session, monkeypatch, tmp_path
):
    """仕事目標の匿名化エクスポートは、既存の全period_key分のgoal_retrospectiveについて
    匿名化版を再生成する（総括レポート専用のgenerate_retrospectiveは仕事目標を拒否するため、
    work_report_serviceのperiod別生成を用いる。データ構造編7.1「仕事目標の場合」）。"""
    from app.services import work_report_service

    # bodyはAI応答の生テキストではなく、見出しでパースした値からテンプレート組み立てする
    # 設計（ロジック・プロンプト編22.6）のため、モック応答は固定見出しを含む形にする。
    normal_response = (
        "## 業務内容の要約\n通常版\n\n"
        "## 達成度\n3\n\n"
        "## 達成状況の振り返り\n通常版の振り返り\n\n"
        "## 来月の目標\n通常版の目標\n\n"
        "## 報告・連絡事項\n"
    )
    anonymized_response = (
        "## 業務内容の要約\n匿名化された内容\n\n"
        "## 達成度\n3\n\n"
        "## 達成状況の振り返り\n匿名化された振り返り\n\n"
        "## 次半期の目標\n匿名化された目標"
    )

    monkeypatch.setattr(export_service, "EXPORT_DIR", tmp_path)
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch, response=normal_response)
    work_report_service.generate_monthly_report(
        seeded_session, goal, period_key="2026-01", today=dt.date(2026, 2, 1)
    )
    work_report_service.generate_semiannual_review(
        seeded_session, goal, period_key="2026-H1", today=dt.date(2026, 8, 1)
    )
    seeded_session.commit()

    _stub_send_message(monkeypatch, response=anonymized_response)
    export_service.execute_export(
        seeded_session, goal, export_service.ExportSelection(), anonymize=True
    )

    anonymized = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(),
        today=dt.date(2026, 8, 1),
        treat_holiday_as_buffer=True,
        anonymized=True,
    )
    assert len(anonymized["retrospectives"]) == 2
    assert all("匿名化された内容" in r["body"] for r in anonymized["retrospectives"])

    # 匿名化版とは別に、元の非匿名化版は削除されず残っている（データ構造編7.3）。
    original = export_service.build_export_data(
        seeded_session,
        goal,
        export_service.ExportSelection(),
        today=dt.date(2026, 8, 1),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    assert all("通常版" in r["body"] for r in original["retrospectives"])
