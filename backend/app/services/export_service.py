"""ナレッジエクスポート（設計書データ構造編7章、仕様書6.10 SC-13、
実装フェーズ分割計画書Phase10）。

日記本文・AI対話履歴は仕様書6.10の出力項目選択に列挙されているが、データ構造編7.1の
JSONスキーマ例には対応するフィールドが無い（既定で除外される項目のため「概要」の例示に
含まれていないと解釈する）。選択された場合は7.1のスキーマを拡張し、"diaries"・
"ai_dialogue" キーを追加する（下記ExportSelectionのコメント参照）。
"""

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import EXPORT_DIR
from app.constants.enums import ChatRole, Granularity, PassingScoreType, RecordState
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import ChatMessage, DailyRecord, StudyLog, WeeklySummary
from app.services import (
    baseline_service,
    cycle_service,
    export_progress,
    goal_service,
    material_service,
    metrics_service,
    retrospective_service,
    weekly_summary_service,
)

#: エクスポートファイル名に使えない文字を除去するための正規表現（目標名に含まれうる
#: ファイルシステム予約文字への対策）。
_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')

#: schema_versionは固定文字列とする（設計書データ構造編9章 未決事項D-04、2026-08-25解消）。
#: 単一利用者・ローカル運用のv1では複数版の共存・自動移行を扱わない。スキーマ変更時に
#: この値を上げ、その時点でインポート側の移行方針を再検討する。
SCHEMA_VERSION = "1.0"

_RESULT_LABELS = {"PASS": "合格", "FAIL": "不合格", "PENDING": "未判定"}
_REASON_LABELS = {
    "INITIAL": "初期設定",
    "REPLAN": "リプラン",
    "EXAM_DATE_FIXED": "受験日確定",
    "MATERIAL_CHANGED": "教材変更",
    "CYCLE_CHANGED": "周回数変更",
}


@dataclass(frozen=True)
class ExportSelection:
    """出力項目選択（仕様書6.10）。既定値は同節の表に合わせ、日記本文・AI対話履歴のみ
    既定で除外する。"""

    goal_overview: bool = True
    materials: bool = True
    summary: bool = True
    daily_records: bool = True
    quality_trend: bool = True
    replan_history: bool = True
    weekly_summaries: bool = True
    diary: bool = False
    ai_dialogue: bool = False
    exam_results: bool = True
    retrospective: bool = True


@dataclass(frozen=True)
class ExportContent:
    data: dict
    markdown: str
    markdown_path: Path | None = None
    json_path: Path | None = None


def _build_goal_and_subjects(goal: Goal) -> tuple[dict, list[dict]]:
    goal_data = {
        "name": goal.name,
        "start_date": goal.start_date.isoformat(),
        "closed_at": goal.closed_at.isoformat() if goal.closed_at else None,
        "status": goal.status.value,
    }
    subjects = [
        {
            "name": subject.name,
            "exam_date": material_service.effective_exam_date(subject).isoformat(),
            "passing_score": subject.passing_score,
            "passing_score_type": subject.passing_score_type.value,
            "passing_score_max": subject.passing_score_max,
        }
        for subject in sorted(goal.exam_subjects, key=lambda s: s.display_order)
    ]
    return goal_data, subjects


def _format_passing_score(subject_data: dict) -> str:
    """合格基準をMarkdown表示用に整形する（百分率は「%」、点数は「/満点点」表記）。"""
    passing_score = subject_data["passing_score"]
    if passing_score is None:
        return "未設定"
    if (
        subject_data["passing_score_type"] == PassingScoreType.RAW_SCORE
        and subject_data["passing_score_max"]
    ):
        return f"{passing_score:g}/{subject_data['passing_score_max']:g}点"
    return f"{passing_score:g}%"


def _build_materials(session: Session, materials: list[Material]) -> list[dict]:
    result = []
    for material in materials:
        progress = cycle_service.get_material_progress(session, material)
        completed_cycles = cycle_service.compute_completed_cycles(material, progress)
        result.append(
            {
                "name": material.name,
                "unit": material.unit_label,
                "total_amount": material.total_amount,
                "planned_cycles": material.planned_cycles,
                "completed_amount": progress.completed,
                "completed_cycles": completed_cycles,
                "start_date": material.start_date.isoformat(),
                "due_date": material.due_date.isoformat(),
                "required_block_minutes": material.required_block_minutes,
                "required_environment": material.required_environment.value,
            }
        )
    return result


def _build_summary(
    session: Session, goal: Goal, today: dt.date, treat_holiday_as_buffer: bool
) -> dict:
    material_ids = [material.id for material in goal.materials]
    study_summary = metrics_service.compute_study_summary(session, material_ids)
    total_minutes = study_summary.total_minutes
    study_days = study_summary.study_days
    return {
        "total_minutes": total_minutes,
        "study_days": study_days,
        "report_rate": metrics_service.compute_report_rate(session, goal, today),
        "buffer_usage_rate": metrics_service.compute_buffer_usage_rate(
            session, goal, today, treat_holiday_as_buffer
        ),
        "replan_count": metrics_service.compute_replan_count(session, goal),
        "average_minutes_per_day": (total_minutes / study_days) if study_days else 0.0,
    }


def _build_daily_records(session: Session, goal: Goal) -> list[dict]:
    material_ids = [material.id for material in goal.materials]
    if not material_ids:
        return []
    material_names = {material.id: material.name for material in goal.materials}
    rows = (
        session.query(
            DailyRecord.record_date,
            StudyLog.material_id,
            StudyLog.minutes_spent,
            StudyLog.amount_completed,
            StudyLog.cycle_number,
            StudyLog.quality_value,
        )
        .join(StudyLog, StudyLog.daily_record_id == DailyRecord.id)
        .filter(StudyLog.material_id.in_(material_ids))
        .order_by(DailyRecord.record_date)
        .all()
    )
    return [
        {
            "date": record_date.isoformat(),
            "material": material_names[material_id],
            "minutes": minutes,
            "amount": amount,
            "cycle": cycle,
            "quality": quality,
        }
        for record_date, material_id, minutes, amount, cycle, quality in rows
    ]


def _build_quality_trend(session: Session, materials: list[Material]) -> list[dict]:
    result = []
    for material in materials:
        trend = metrics_service.compute_quality_trend(session, material.id, Granularity.MONTH)
        for cycle_number in sorted(trend):
            result.append(
                {
                    "material": material.name,
                    "cycle": cycle_number,
                    "series": [
                        {"date": point.period_start.isoformat(), "value": point.value}
                        for point in trend[cycle_number]
                    ],
                }
            )
    return result


def _build_replan_history(session: Session, goal: Goal) -> list[dict]:
    baselines = goal_service.get_baselines(session, goal)
    changes = baseline_service.compute_baseline_changes(baselines)
    material_names = {material.id: material.name for material in goal.materials}
    return [
        {
            "date": change.effective_from.isoformat(),
            "material": material_names.get(change.material_id, ""),
            "reason": change.reason.value,
            "quota_before": change.quota_before,
            "quota_after": change.quota_after,
            "remaining": change.remaining_at_baseline,
            "plan_days": change.plan_days_at_baseline,
        }
        for change in changes
    ]


def _build_weekly_summaries(session: Session, goal: Goal, *, anonymized: bool) -> list[dict]:
    rows = (
        session.query(WeeklySummary)
        .filter(WeeklySummary.goal_id == goal.id, WeeklySummary.is_anonymized == anonymized)
        .order_by(WeeklySummary.week_start_date)
        .all()
    )
    return [
        {"week_start": row.week_start_date.isoformat(), "body": row.summary_body} for row in rows
    ]


def _build_results(goal: Goal) -> list[dict]:
    result = []
    for subject in sorted(goal.exam_subjects, key=lambda s: s.display_order):
        if subject.exam_result is None:
            continue
        result.append(
            {
                "subject": subject.name,
                "result": subject.exam_result.result.value,
                "score": subject.exam_result.score,
            }
        )
    return result


def _build_diaries(session: Session, goal: Goal) -> list[dict]:
    material_ids = [material.id for material in goal.materials]
    if not material_ids:
        return []
    records = (
        session.query(DailyRecord)
        .join(StudyLog, StudyLog.daily_record_id == DailyRecord.id)
        .filter(
            StudyLog.material_id.in_(material_ids),
            DailyRecord.record_state == RecordState.REPORTED,
        )
        .distinct()
        .order_by(DailyRecord.record_date)
        .all()
    )
    return [
        {
            "date": record.record_date.isoformat(),
            "body": record.diary_body or "",
            "learned": record.diary_learned or "",
        }
        for record in records
    ]


def _build_ai_dialogue(session: Session, goal: Goal) -> list[dict]:
    material_ids = [material.id for material in goal.materials]
    if not material_ids:
        return []
    record_ids = {
        row[0]
        for row in session.query(DailyRecord.id)
        .join(StudyLog, StudyLog.daily_record_id == DailyRecord.id)
        .filter(StudyLog.material_id.in_(material_ids))
        .distinct()
    }
    if not record_ids:
        return []
    rows = (
        session.query(DailyRecord.record_date, ChatMessage.role, ChatMessage.content)
        .join(ChatMessage, ChatMessage.daily_record_id == DailyRecord.id)
        .filter(DailyRecord.id.in_(record_ids))
        .order_by(DailyRecord.record_date, ChatMessage.sequence)
        .all()
    )
    return [
        {
            "date": record_date.isoformat(),
            "role": role.value if isinstance(role, ChatRole) else role,
            "content": content,
        }
        for record_date, role, content in rows
    ]


def build_export_data(
    session: Session,
    goal: Goal,
    selection: ExportSelection,
    *,
    today: dt.date,
    treat_holiday_as_buffer: bool,
    anonymized: bool,
) -> dict:
    """データ構造編7.1のJSONスキーマに沿ってエクスポートデータを組み立てる。

    anonymized=True の場合、weekly_summaries・retrospective は匿名化版レコードのみを参照する
    （元版へフォールバックしない。フォールバックすると匿名化の目的が果たせないため、
    未生成であれば空のまま返す。呼び出し元 execute_export が事前に匿名化版を生成する）。
    """
    materials = [material for material in goal.materials if material.is_active]
    data: dict = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": dt.datetime.now(dt.UTC).isoformat(),
        "anonymized": anonymized,
    }

    if selection.goal_overview:
        goal_data, subjects = _build_goal_and_subjects(goal)
        data["goal"] = goal_data
        data["subjects"] = subjects
    if selection.materials:
        data["materials"] = _build_materials(session, materials)
    if selection.summary:
        data["summary"] = _build_summary(session, goal, today, treat_holiday_as_buffer)
    if selection.daily_records:
        data["daily_records"] = _build_daily_records(session, goal)
    if selection.quality_trend:
        data["quality_trend"] = _build_quality_trend(session, materials)
    if selection.replan_history:
        data["replan_history"] = _build_replan_history(session, goal)
    if selection.weekly_summaries:
        data["weekly_summaries"] = _build_weekly_summaries(session, goal, anonymized=anonymized)
    if selection.exam_results:
        data["results"] = _build_results(goal)
    if selection.retrospective:
        retrospective = retrospective_service.get_latest_retrospective(
            session, goal, anonymized=anonymized
        )
        data["retrospective"] = retrospective.body if retrospective is not None else None
    # 匿名化時は日記本文・AI対話履歴を選択有無に関わらず全面除外する（実装フェーズ分割
    # 計画書Phase10完了条件「匿名化時に日記本文とAI対話履歴が除外される」）。
    if selection.diary and not anonymized:
        data["diaries"] = _build_diaries(session, goal)
    if selection.ai_dialogue and not anonymized:
        data["ai_dialogue"] = _build_ai_dialogue(session, goal)

    return data


def render_markdown(data: dict, selection: ExportSelection) -> str:
    """データ構造編7.2のMarkdown構成に沿って本文を生成する。"""
    sections: list[str] = []

    if "goal" in data:
        goal_data = data["goal"]
        subjects_text = "\n".join(
            f"- {s['name']}（受験日: {s['exam_date']}、合格基準: {_format_passing_score(s)}）"
            for s in data.get("subjects", [])
        ) or "（試験科目未登録）"
        closed_at_text = goal_data["closed_at"] or "（未クローズ）"
        sections.append(
            "## 1. 概要\n\n"
            f"- 試験名: {goal_data['name']}\n"
            f"- 学習期間: {goal_data['start_date']} 〜 {closed_at_text}\n"
            f"- 状態: {goal_data['status']}\n\n{subjects_text}"
        )

    if "retrospective" in data:
        body = data["retrospective"] or "（総括レポートは未生成です）"
        sections.append(f"## 2. 総括\n\n{body}")

    if "summary" in data:
        s = data["summary"]
        sections.append(
            "## 3. 学習量\n\n"
            f"- 総投下時間: {s['total_minutes'] / 60:.1f}時間\n"
            f"- 学習日数: {s['study_days']}日\n"
            f"- 報告率: {s['report_rate']:.0%}\n"
            f"- 平均時間: {s['average_minutes_per_day']:.1f}分/日"
        )

    if "materials" in data:
        rows = "\n".join(
            f"| {m['name']} | {m['total_amount']}{m['unit']} | {m['planned_cycles']} | "
            f"{m['completed_cycles']} | {m['due_date']} |"
            for m in data["materials"]
        )
        sections.append(
            "## 4. 教材構成\n\n"
            "| 教材 | 総量 | 予定周回 | 実績周回 | 締切 |\n| --- | --- | --- | --- | --- |\n"
            f"{rows}"
        )

    if "quality_trend" in data:
        lines = []
        for entry in data["quality_trend"]:
            points = "、".join(f"{p['date']}: {p['value']:.1f}" for p in entry["series"])
            lines.append(f"- {entry['material']} {entry['cycle']}周目: {points}")
        sections.append("## 5. 品質の推移\n\n" + ("\n".join(lines) or "（記録なし）"))

    if "replan_history" in data:
        rows = "\n".join(
            f"| {r['date']} | {r['material']} | {_REASON_LABELS.get(r['reason'], r['reason'])} | "
            f"{r['quota_before']} → {r['quota_after']} |"
            for r in data["replan_history"]
        )
        sections.append(
            "## 6. 計画の修正履歴\n\n"
            "| 日時 | 教材 | 契機 | 変更前後のノルマ |\n| --- | --- | --- | --- |\n"
            f"{rows}"
        )

    if "weekly_summaries" in data:
        lines = "\n\n".join(
            f"### {w['week_start']}\n\n{w['body']}" for w in data["weekly_summaries"]
        )
        sections.append("## 7. 週ごとの経過\n\n" + (lines or "（記録なし）"))

    if "daily_records" in data:
        rows = "\n".join(
            f"| {r['date']} | {r['material']} | {r['minutes'] or '-'} | {r['amount']} | "
            f"{r['cycle']} | {r['quality'] if r['quality'] is not None else '-'} |"
            for r in data["daily_records"]
        )
        sections.append(
            "## 8. 付録：日別実績\n\n"
            "| 日付 | 教材 | 投下時間(分) | 完了量 | 周回 | 品質指標 |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            f"{rows}"
        )

    if "results" in data:
        rows = "\n".join(
            f"| {r['subject']} | {_RESULT_LABELS.get(r['result'], r['result'])} | "
            f"{r['score'] if r['score'] is not None else '-'} |"
            for r in data["results"]
        )
        sections.append(
            "## 9. 受験結果\n\n| 科目 | 合否 | 得点 |\n| --- | --- | --- |\n" + rows
        )

    if "diaries" in data:
        lines = "\n\n".join(
            f"### {d['date']}\n\n{d['body']}\n\n学んだこと: {d['learned']}"
            for d in data["diaries"]
        )
        sections.append("## 10. 日記\n\n" + (lines or "（記録なし）"))

    if "ai_dialogue" in data:
        lines = "\n".join(
            f"- [{d['date']}] {d['role']}: {d['content']}" for d in data["ai_dialogue"]
        )
        sections.append("## 11. AI対話履歴\n\n" + (lines or "（記録なし）"))

    title = data.get("goal", {}).get("name", "ナレッジエクスポート")
    return f"# {title}\n\n" + "\n\n".join(sections)


def _safe_filename_fragment(name: str) -> str:
    return _UNSAFE_FILENAME_CHARS.sub("_", name).strip() or "goal"


def write_export_files(goal: Goal, content: ExportContent) -> tuple[Path, Path]:
    """Markdown・JSONの両形式をファイルへ出力する（仕様書6.10「ファイルの出力」、
    データ構造編8章ディレクトリ構成「data/ ...エクスポート」）。
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    base_name = f"{_safe_filename_fragment(goal.name)}_{timestamp}"
    markdown_path = EXPORT_DIR / f"{base_name}.md"
    json_path = EXPORT_DIR / f"{base_name}.json"

    markdown_path.write_text(content.markdown, encoding="utf-8")
    json_path.write_text(json.dumps(content.data, ensure_ascii=False, indent=2), encoding="utf-8")
    return markdown_path, json_path


def execute_export(
    session: Session,
    goal: Goal,
    selection: ExportSelection,
    *,
    anonymize: bool,
) -> ExportContent:
    """ナレッジエクスポートを実行する（仕様書6.10「操作: 総括レポートの生成および再生成、
    出力項目の選択、プレビュー表示、ファイルの出力」のうち実行部分）。

    anonymize=True の場合、事前に週次要約・総括レポートの匿名化版を生成してから
    組み立てる（データ構造編7.3）。既存の匿名化版がある場合は最新内容へ更新する。
    プレビュー（GET .../preview）はbuild_export_dataのみを呼び、本関数（ファイル書き出しと
    匿名化再生成を伴う実行）とは区別する。

    複数回のAI呼び出し（週次要約1件ずつ＋総括レポート）を伴うため、進捗を
    app.services.export_progress へ記録する（実装フェーズ分割計画書Phase10注意点）。
    フロントエンドはGET /goals/{goal_id}/knowledge-export/progress をポーリングして表示する。
    """
    today = goal_service.resolve_today(session)
    treat_holiday_as_buffer = goal_service.resolve_treat_holiday_as_buffer(session)

    if anonymize:
        total = weekly_summary_service.count_pending_anonymization_weeks(session, goal) + 1
        export_progress.start(goal.id, total=total)
        try:
            weekly_summary_service.regenerate_all_weekly_summaries_anonymized(
                session, goal, on_progress=lambda: export_progress.advance(goal.id)
            )
            retrospective_service.generate_retrospective(
                session, goal, today=today, anonymize=True
            )
            export_progress.advance(goal.id)
        finally:
            export_progress.finish(goal.id)

    data = build_export_data(
        session,
        goal,
        selection,
        today=today,
        treat_holiday_as_buffer=treat_holiday_as_buffer,
        anonymized=anonymize,
    )
    markdown = render_markdown(data, selection)
    content = ExportContent(data=data, markdown=markdown)
    markdown_path, json_path = write_export_files(goal, content)
    return ExportContent(
        data=data, markdown=markdown, markdown_path=markdown_path, json_path=json_path
    )
