"""export_service_common のテスト（設計書データ構造編7章、仕様書6.10 SC-13、
実装フェーズ分割計画書S02）。

元ファイル（test_export_service.py）のテストはいずれも単一カテゴリ（EXAM/READING/WORK）の
目標を対象にしていたため、カテゴリを問わない共通の挙動（基本辞書の3キーが常に残ること・
ファイル出力機構）のみが本ファイルの対象となる。カテゴリ別の組み立て・Markdown生成の
テストはtest_export_service_exam.py・_reading.py・_work.pyを参照（実装フェーズ分割計画書
S02、test_export_service.pyからの分割）。
"""

import datetime as dt

from app.constants.enums import GoalStatus
from app.models.goal import Goal
from app.services import export_service_common
from app.services.export_service_common import ExportSelection


def _make_goal(session, name="目標A"):
    goal = Goal(
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    return goal


def test_build_export_data_omits_unselected_sections(seeded_session):
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

    assert set(data.keys()) == {"schema_version", "exported_at", "anonymized"}


def test_execute_export_writes_markdown_and_json_files(seeded_session, monkeypatch, tmp_path):
    monkeypatch.setattr(export_service_common, "EXPORT_DIR", tmp_path)
    goal = _make_goal(seeded_session)

    content = export_service_common.execute_export(
        seeded_session, goal, ExportSelection(), anonymize=False
    )

    assert content.markdown_path.exists()
    assert content.json_path.exists()
    assert content.markdown_path.read_text(encoding="utf-8") == content.markdown
