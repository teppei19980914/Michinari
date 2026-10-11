"""ナレッジエクスポートのうち仕事（WORK）固有の処理（設計書データ構造編7章、
仕様書6.10 SC-13）。共通処理は`export_service_common.py`を参照（実装フェーズ分割計画書
S02、`export_service.py`からの分割）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.export_markdown import (
    EXPORT_DEFAULT_TITLE,
    EXPORT_HEADING_APPENDIX_WORK_LOGS,
    EXPORT_HEADING_OVERVIEW,
    EXPORT_HEADING_RECORD_VOLUME,
    EXPORT_HEADING_WORK_REPORTS,
    EXPORT_LABEL_ASSIGNMENT_NAME,
    EXPORT_LABEL_CLIENT_NAME,
    EXPORT_LABEL_EXPECTED_CONTENT,
    EXPORT_LABEL_MAX_STREAK,
    EXPORT_LABEL_RECORD_DAYS,
    EXPORT_LABEL_START_DATE,
    EXPORT_PLACEHOLDER_NO_WORK_REPORTS,
    EXPORT_PLACEHOLDER_UNREGISTERED,
    EXPORT_TABLE_HEAD_WORK_LOGS,
    EXPORT_UNIT_DAYS,
)
from app.models.goal import Goal
from app.models.record import DailyRecord, WorkLog
from app.models.retrospective import GoalRetrospective
from app.models.work import WorkAssignment
from app.services.export_service_common import ExportSelection
from app.services.export_service_reading import _compute_max_streak_days


def _build_work_assignment(goal: Goal, work_assignment: WorkAssignment) -> dict:
    """案件名（goal.name）は必須のため常に含める。client_nameは「取引先・案件の呼称」用の
    任意項目であり、案件名の代わりにはならない（frontend/src/locales/ja.json
    goals.workAssignment.clientNameLabel参照）。"""
    return {
        "name": goal.name,
        "client_name": work_assignment.client_name,
        "expected_content": work_assignment.expected_content,
        "start_date": work_assignment.start_date.isoformat(),
    }


def _work_log_dates(session: Session, work_assignment: WorkAssignment) -> set[dt.date]:
    return {
        row[0]
        for row in session.query(DailyRecord.record_date)
        .join(WorkLog, WorkLog.daily_record_id == DailyRecord.id)
        .filter(WorkLog.work_assignment_id == work_assignment.id)
        .distinct()
    }


def _build_work_summary(session: Session, work_assignment: WorkAssignment) -> dict:
    """仕事サマリ（設計書データ構造編7.1「仕事目標の場合」）：記録日数・最長連続記録日数。
    読書と同じ定義のため_compute_max_streak_daysを流用する（CLAUDE.md DRYの原則）。"""
    record_dates = _work_log_dates(session, work_assignment)
    return {
        "record_days": len(record_dates),
        "max_streak_days": _compute_max_streak_days(record_dates),
    }


def _build_work_daily_records(session: Session, work_assignment: WorkAssignment) -> list[dict]:
    """日別の業務記録一覧（仕様書6.10「実績推移」は日別の業務記録一覧と読み替え）。"""
    rows = (
        session.query(DailyRecord.record_date, WorkLog.body)
        .join(WorkLog, WorkLog.daily_record_id == DailyRecord.id)
        .filter(WorkLog.work_assignment_id == work_assignment.id)
        .order_by(DailyRecord.record_date)
        .all()
    )
    return [{"date": record_date.isoformat(), "body": body} for record_date, body in rows]


def build_work_retrospectives(session: Session, goal: Goal, *, anonymized: bool) -> list[dict]:
    """対象goalに紐づく全goal_retrospective（period_type問わず）を期間の新しい順に列挙する
    （設計書データ構造編7.1「仕事目標の場合」。読書と異なり単一文字列ではなく配列を用いる。
    要件定義書R-80「案件単位で生成」・R-81「ナレッジエクスポート対象」）。

    `export_service_common.execute_export`の匿名化分岐（WORK）からも呼ばれる（複数モジュール
    から参照されるため、分割前のアンダースコア付き名称から変更した。実装フェーズ分割計画書
    S02）。
    """
    rows = (
        session.query(GoalRetrospective)
        .filter(GoalRetrospective.goal_id == goal.id, GoalRetrospective.is_anonymized == anonymized)
        .order_by(GoalRetrospective.period_key.desc())
        .all()
    )
    return [
        {
            "period_type": row.period_type.value if row.period_type is not None else None,
            "period_key": row.period_key,
            "body": row.body,
            "generated_at": row.generated_at.isoformat(),
        }
        for row in rows
    ]


def build_work_export_data(
    session: Session, goal: Goal, selection: ExportSelection, *, anonymized: bool, data: dict
) -> dict:
    """仕事目標（category=WORK）向けのエクスポートデータ組み立て（仕様書6.10、
    設計書データ構造編7.1「仕事目標の場合」）。

    教材構成・品質指標推移・受験結果・週次要約・リプラン履歴は該当データを持たないため
    出力しない。日記本文・AI対話履歴も、業務記録（daily_records）がその代替であるため
    出力しない（読書と同じ理由、データ構造編7.3）。
    """
    work_assignment = goal.work_assignment
    if selection.goal_overview and work_assignment is not None:
        data["work_assignment"] = _build_work_assignment(goal, work_assignment)
    if selection.summary and work_assignment is not None:
        data["summary"] = _build_work_summary(session, work_assignment)
    if selection.daily_records and not anonymized and work_assignment is not None:
        data["daily_records"] = _build_work_daily_records(session, work_assignment)
    if selection.retrospective:
        data["retrospectives"] = build_work_retrospectives(session, goal, anonymized=anonymized)
    return data


def render_work_markdown(data: dict) -> str:
    """仕事目標のMarkdown構成（設計書データ構造編7.2「仕事目標の場合」）。"""
    sections: list[str] = []

    if "work_assignment" in data:
        wa = data["work_assignment"]
        sections.append(
            f"{EXPORT_HEADING_OVERVIEW}\n\n"
            f"{EXPORT_LABEL_ASSIGNMENT_NAME}{wa['name']}\n"
            f"{EXPORT_LABEL_CLIENT_NAME}{wa['client_name'] or EXPORT_PLACEHOLDER_UNREGISTERED}\n"
            f"{EXPORT_LABEL_EXPECTED_CONTENT}{wa['expected_content']}\n"
            f"{EXPORT_LABEL_START_DATE}{wa['start_date']}"
        )

    if "retrospectives" in data:
        retrospectives = data["retrospectives"]
        if retrospectives:
            lines = "\n\n".join(
                f"### {r['period_key']}（{r['period_type']}）\n\n{r['body']}"
                for r in retrospectives
            )
        else:
            lines = EXPORT_PLACEHOLDER_NO_WORK_REPORTS
        sections.append(f"{EXPORT_HEADING_WORK_REPORTS}\n\n{lines}")

    if "summary" in data:
        s = data["summary"]
        sections.append(
            f"{EXPORT_HEADING_RECORD_VOLUME}\n\n"
            f"{EXPORT_LABEL_RECORD_DAYS}{s['record_days']}{EXPORT_UNIT_DAYS}\n"
            f"{EXPORT_LABEL_MAX_STREAK}{s['max_streak_days']}{EXPORT_UNIT_DAYS}"
        )

    if "daily_records" in data:
        rows = "\n".join(f"| {r['date']} | {r['body']} |" for r in data["daily_records"])
        sections.append(
            f"{EXPORT_HEADING_APPENDIX_WORK_LOGS}\n\n"
            f"{EXPORT_TABLE_HEAD_WORK_LOGS}\n| --- | --- |\n{rows}"
        )

    title = data.get("work_assignment", {}).get("name") or EXPORT_DEFAULT_TITLE
    return f"# {title}\n\n" + "\n\n".join(sections)
