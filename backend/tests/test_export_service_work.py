"""export_service_work のテスト（設計書データ構造編7章、仕様書6.10 SC-13、
実装フェーズ分割計画書S02）。test_export_service.pyからの分割（実装フェーズ分割計画書S02）。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.constants.enums import GoalCategory, GoalStatus
from app.models.goal import Goal
from app.models.record import DailyRecord, WorkLog
from app.models.work import WorkAssignment
from app.services import export_service_common, work_report_service
from app.services.export_service_common import ExportSelection


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


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

    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
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

    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(daily_records=True),
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
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch, response="生成結果")
    work_report_service.generate_monthly_report(
        seeded_session, goal, period_key="2026-01", today=dt.date(2026, 2, 1)
    )
    work_report_service.generate_monthly_report(
        seeded_session, goal, period_key="2026-02", today=dt.date(2026, 3, 1)
    )

    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
        today=dt.date(2026, 3, 1),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )

    assert [r["period_key"] for r in data["retrospectives"]] == ["2026-02", "2026-01"]
    assert data["retrospectives"][0]["period_type"] == "MONTHLY"


def test_build_export_data_for_work_goal_omits_unselected_sections(seeded_session):
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)

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


# --- render_markdown（仕事目標） ---


def test_render_markdown_for_work_goal_includes_work_headings(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment, dt.date(2026, 1, 1))

    selection = ExportSelection()
    data = export_service_common.build_export_data(
        seeded_session,
        goal,
        selection,
        today=dt.date(2026, 1, 5),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    markdown = export_service_common.render_markdown(data, selection, GoalCategory.WORK)

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
    markdown = export_service_common.render_markdown(data, selection, GoalCategory.WORK)

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

    monkeypatch.setattr(export_service_common, "EXPORT_DIR", tmp_path)
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
    export_service_common.execute_export(seeded_session, goal, ExportSelection(), anonymize=True)

    anonymized = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
        today=dt.date(2026, 8, 1),
        treat_holiday_as_buffer=True,
        anonymized=True,
    )
    assert len(anonymized["retrospectives"]) == 2
    assert all("匿名化された内容" in r["body"] for r in anonymized["retrospectives"])

    # 匿名化版とは別に、元の非匿名化版は削除されず残っている（データ構造編7.3）。
    original = export_service_common.build_export_data(
        seeded_session,
        goal,
        ExportSelection(),
        today=dt.date(2026, 8, 1),
        treat_holiday_as_buffer=True,
        anonymized=False,
    )
    assert all("通常版" in r["body"] for r in original["retrospectives"])
