"""export_service_reading のテスト（設計書データ構造編7章、仕様書6.10 SC-13、
実装フェーズ分割計画書S02）。test_export_service.pyからの分割（実装フェーズ分割計画書S02）。
"""

import datetime as dt

from app.constants.enums import GoalCategory
from app.models.record import DailyRecord, ReadingLog
from app.services import export_service_common
from app.services.export_service_common import ExportSelection
from tests import reading_helpers


def _make_reading_goal(session, name="読書目標A"):
    return reading_helpers.make_reading_goal(session, name=name)


def _make_book(session, goal, **overrides):
    """エクスポートの検証では著者名と読了目標日を固定したいため、既定値を上書きする。"""
    defaults = dict(author="著者A", due_date=dt.date(2026, 3, 1))
    defaults.update(overrides)
    return reading_helpers.make_book(session, goal.id, **defaults)


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
        current_page=50,
    )
    defaults.update(overrides)
    session.add(ReadingLog(**defaults))
    session.flush()
    return record


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

    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
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

    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(daily_records=True),
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=True,
    )

    assert "daily_records" not in data


def test_build_export_data_for_reading_goal_with_no_reading_logs(seeded_session):
    goal = _make_reading_goal(seeded_session)
    _make_book(seeded_session, goal)

    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert data["summary"] == {"record_days": 0, "max_streak_days": 0}
    assert data["daily_records"] == []


def test_build_export_data_for_reading_goal_omits_unselected_sections(seeded_session):
    goal = _make_reading_goal(seeded_session)
    _make_book(seeded_session, goal)

    selection = ExportSelection(
        goal_overview=False, summary=False, daily_records=False, retrospective=False
    )
    data = export_service_common.build_export_data(
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

    selection = ExportSelection()
    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    markdown = export_service_common.render_markdown(data, selection, GoalCategory.READING)

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

    selection = ExportSelection(
        goal_overview=False, summary=False, daily_records=False, retrospective=False
    )
    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    markdown = export_service_common.render_markdown(data, selection, GoalCategory.READING)

    assert "## 1. 概要" not in markdown
    assert "## 2. 読了レポート" not in markdown
    assert "## 3. 記録量" not in markdown
    assert "## 4. 付録：日別の想起記録" not in markdown
