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
from app.constants.enums import (
    AiPurpose,
    ChatRole,
    GoalCategory,
    Granularity,
    PassingScoreType,
    RecordState,
    RetrospectivePeriodType,
)
from app.models.book import Book
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import (
    ChatMessage,
    DailyGoalDiary,
    DailyRecord,
    ReadingLog,
    StudyLog,
    StudyLogSlotTime,
    WeeklySummary,
    WorkLog,
)
from app.models.resource import ResourceSlot
from app.models.retrospective import GoalRetrospective
from app.models.work import WorkAssignment
from app.services import (
    baseline_service,
    cycle_service,
    export_progress,
    goal_service,
    material_service,
    metrics_service,
    retrospective_service,
    weekly_summary_service,
    work_report_service,
)

#: エクスポートファイル名に使えない文字を除去するための正規表現（目標名に含まれうる
#: ファイルシステム予約文字への対策）。
_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')

#: schema_versionは固定文字列とする（設計書データ構造編9章 未決事項D-04、2026-08-25解消）。
#: 単一利用者・ローカル運用のv1では複数版の共存・自動移行を扱わない。スキーマ変更時に
#: この値を上げ、その時点でインポート側の移行方針を再検討する。
#: 1.1: リソース配分のスロット単位化に伴い、実績推移へ時間枠別内訳（slot_minutes）を追加。
SCHEMA_VERSION = "1.1"

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
    """実績推移（データ構造編7.1 daily_records）。

    投下時間は教材ごとの合計（minutes）に加え、時間枠別の内訳（slot_minutes）も出力する
    （schema_version 1.1）。時間枠が削除済みの内訳は名称を持たないため slot を null とする。
    """
    material_ids = [material.id for material in goal.materials]
    if not material_ids:
        return []
    material_names = {material.id: material.name for material in goal.materials}
    rows = (
        session.query(
            DailyRecord.record_date,
            StudyLog.id,
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
    breakdown = _build_slot_minutes_by_study_log(session, [row[1] for row in rows])
    return [
        {
            "date": record_date.isoformat(),
            "material": material_names[material_id],
            "minutes": minutes,
            "slot_minutes": breakdown.get(study_log_id, []),
            "amount": amount,
            "cycle": cycle,
            "quality": quality,
        }
        for record_date, study_log_id, material_id, minutes, amount, cycle, quality in rows
    ]


def _build_slot_minutes_by_study_log(
    session: Session, study_log_ids: list[int]
) -> dict[int, list[dict]]:
    """study_log_id → 時間枠別内訳。1回のクエリでまとめて引く（N+1禁止）。"""
    if not study_log_ids:
        return {}
    rows = (
        session.query(
            StudyLogSlotTime.study_log_id,
            StudyLogSlotTime.minutes,
            ResourceSlot.name,
        )
        .outerjoin(ResourceSlot, ResourceSlot.id == StudyLogSlotTime.slot_id)
        .filter(StudyLogSlotTime.study_log_id.in_(study_log_ids))
        .order_by(StudyLogSlotTime.study_log_id, StudyLogSlotTime.id)
        .all()
    )
    result: dict[int, list[dict]] = {}
    for study_log_id, minutes, slot_name in rows:
        result.setdefault(study_log_id, []).append({"slot": slot_name, "minutes": minutes})
    return result


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
    """日記は目標別（DailyGoalDiary）に保持しているため、goal_idで絞り込む
    （複数目標が同時進行していた日に他目標の日記が混入しないようにする、L-04関連）。
    """
    rows = (
        session.query(
            DailyRecord.record_date, DailyGoalDiary.diary_body, DailyGoalDiary.diary_learned
        )
        .join(DailyGoalDiary, DailyGoalDiary.daily_record_id == DailyRecord.id)
        .filter(
            DailyGoalDiary.goal_id == goal.id,
            DailyRecord.exam_record_state == RecordState.REPORTED,
        )
        .order_by(DailyRecord.record_date)
        .all()
    )
    return [
        {
            "date": record_date.isoformat(),
            "body": diary_body or "",
            "learned": diary_learned or "",
        }
        for record_date, diary_body, diary_learned in rows
    ]


def _build_ai_dialogue(session: Session, goal: Goal) -> list[dict]:
    """資格試験目標のAI対話履歴を抽出する（読書・仕事目標はmaterialsを持たないため対象外）。

    Phase26でchat_message.goal_idを追加し目標単位の会話へ分離したことに伴い、直接
    goal_idで絞り込む方式へ変更した。従来はその目標のstudy_logがある日付に絞り込んだ上で
    その日のchat_messageを無条件に取得していたため、同日に他の目標（他カテゴリを含む）の
    日次フィードバック対話があると誤って混入する不具合があった（この目標を選んで出力した
    エクスポートに、他の目標宛ての対話内容が含まれてしまう）。goal_id・purposeの両方で
    絞り込むことで解消する。目標単位分離より前のレガシーメッセージ（goal_id=NULL）は、
    どの目標宛てか技術的に判別不能なため対象外とする（分析タブ「成長記述」で目標を
    手動で割り当てれば、以降のエクスポートで対象に含まれる）。
    """
    if not goal.materials:
        return []
    rows = (
        session.query(DailyRecord.record_date, ChatMessage.role, ChatMessage.content)
        .join(ChatMessage, ChatMessage.daily_record_id == DailyRecord.id)
        .filter(ChatMessage.goal_id == goal.id, ChatMessage.purpose == AiPurpose.DAILY_FEEDBACK)
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


def _build_book(book: Book) -> dict:
    return {
        "title": book.title,
        "author": book.author,
        "total_pages": book.total_pages,
        "start_date": book.start_date.isoformat(),
        "due_date": book.due_date.isoformat(),
    }


def _reading_log_dates(session: Session, book: Book) -> set[dt.date]:
    return {
        row[0]
        for row in session.query(DailyRecord.record_date)
        .join(ReadingLog, ReadingLog.daily_record_id == DailyRecord.id)
        .filter(ReadingLog.book_id == book.id)
        .distinct()
    }


def _compute_max_streak_days(record_dates: set[dt.date]) -> int:
    if not record_dates:
        return 0
    sorted_dates = sorted(record_dates)
    longest = current = 1
    for previous, current_date in zip(sorted_dates, sorted_dates[1:], strict=False):
        if current_date - previous == dt.timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _build_reading_summary(session: Session, book: Book) -> dict:
    """読書サマリ（設計書データ構造編7.1「読書目標の場合」）：記録日数・最長連続記録日数。"""
    record_dates = _reading_log_dates(session, book)
    return {
        "record_days": len(record_dates),
        "max_streak_days": _compute_max_streak_days(record_dates),
    }


def _build_reading_daily_records(session: Session, book: Book) -> list[dict]:
    """日別の想起記録一覧（仕様書6.10「実績推移」は日別の想起記録一覧と読み替え）。"""
    rows = (
        session.query(
            DailyRecord.record_date,
            ReadingLog.recall_body,
            ReadingLog.pages_read,
            ReadingLog.current_page,
        )
        .join(ReadingLog, ReadingLog.daily_record_id == DailyRecord.id)
        .filter(ReadingLog.book_id == book.id)
        .order_by(DailyRecord.record_date)
        .all()
    )
    return [
        {
            "date": record_date.isoformat(),
            "recall": recall_body,
            "pages_read": pages_read,
            "current_page": current_page,
        }
        for record_date, recall_body, pages_read, current_page in rows
    ]


def _build_reading_export_data(
    session: Session, goal: Goal, selection: ExportSelection, *, anonymized: bool, data: dict
) -> dict:
    """読書目標（category=READING）向けのエクスポートデータ組み立て（仕様書6.10、
    設計書データ構造編7.1「読書目標の場合」）。

    教材構成・品質指標推移・受験結果・週次要約・リプラン履歴は該当データを持たないため
    出力しない。日記本文・AI対話履歴も、想起記録（daily_records）がその代替であるため
    出力しない（データ構造編7.3「日記本文・AI対話履歴は出力から除外する」）。
    """
    book = goal.book
    if selection.goal_overview and book is not None:
        data["book"] = _build_book(book)
    if selection.summary and book is not None:
        data["summary"] = _build_reading_summary(session, book)
    if selection.daily_records and not anonymized and book is not None:
        data["daily_records"] = _build_reading_daily_records(session, book)
    if selection.retrospective:
        retrospective = retrospective_service.get_latest_retrospective(
            session, goal, anonymized=anonymized
        )
        data["retrospective"] = retrospective.body if retrospective is not None else None
    return data


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


def _build_work_retrospectives(session: Session, goal: Goal, *, anonymized: bool) -> list[dict]:
    """対象goalに紐づく全goal_retrospective（period_type問わず）を期間の新しい順に列挙する
    （設計書データ構造編7.1「仕事目標の場合」。読書と異なり単一文字列ではなく配列を用いる。
    要件定義書R-80「案件単位で生成」・R-81「ナレッジエクスポート対象」）。
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


def _build_work_export_data(
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
        data["retrospectives"] = _build_work_retrospectives(session, goal, anonymized=anonymized)
    return data


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
    data: dict = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": dt.datetime.now(dt.UTC).isoformat(),
        "anonymized": anonymized,
    }

    if goal.category == GoalCategory.READING:
        return _build_reading_export_data(
            session, goal, selection, anonymized=anonymized, data=data
        )
    if goal.category == GoalCategory.WORK:
        return _build_work_export_data(session, goal, selection, anonymized=anonymized, data=data)

    materials = [material for material in goal.materials if material.is_active]

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


def _render_reading_markdown(data: dict) -> str:
    """読書目標のMarkdown構成（設計書データ構造編7.2「読書目標の場合」）。"""
    sections: list[str] = []

    if "book" in data:
        book = data["book"]
        sections.append(
            "## 1. 概要\n\n"
            f"- 書名: {book['title']}\n"
            f"- 著者: {book['author'] or '（未登録）'}\n"
            f"- 読了目標日: {book['due_date']}\n"
            f"- 読書期間: {book['start_date']} 〜 {book['due_date']}"
        )

    if "retrospective" in data:
        body = data["retrospective"] or "（読了レポートは未生成です）"
        sections.append(f"## 2. 読了レポート\n\n{body}")

    if "summary" in data:
        s = data["summary"]
        sections.append(
            "## 3. 記録量\n\n"
            f"- 記録日数: {s['record_days']}日\n"
            f"- 最長連続記録日数: {s['max_streak_days']}日"
        )

    if "daily_records" in data:
        rows = "\n".join(
            f"| {r['date']} | {r['recall']} | "
            f"{r['pages_read'] if r['pages_read'] is not None else '-'} | "
            f"{r['current_page'] if r['current_page'] is not None else '-'} |"
            for r in data["daily_records"]
        )
        sections.append(
            "## 4. 付録：日別の想起記録\n\n"
            "| 日付 | 想起内容 | 読んだページ数 | 現在ページ |\n"
            "| --- | --- | --- | --- |\n"
            f"{rows}"
        )

    title = data.get("book", {}).get("title", "ナレッジエクスポート")
    return f"# {title}\n\n" + "\n\n".join(sections)


def _render_work_markdown(data: dict) -> str:
    """仕事目標のMarkdown構成（設計書データ構造編7.2「仕事目標の場合」）。"""
    sections: list[str] = []

    if "work_assignment" in data:
        wa = data["work_assignment"]
        sections.append(
            "## 1. 概要\n\n"
            f"- 案件名: {wa['name']}\n"
            f"- 取引先・案件の呼称: {wa['client_name'] or '（未登録）'}\n"
            f"- 想定業務内容: {wa['expected_content']}\n"
            f"- 着手日: {wa['start_date']}"
        )

    if "retrospectives" in data:
        retrospectives = data["retrospectives"]
        if retrospectives:
            lines = "\n\n".join(
                f"### {r['period_key']}（{r['period_type']}）\n\n{r['body']}"
                for r in retrospectives
            )
        else:
            lines = "（月次報告・半期評価は未生成です）"
        sections.append(f"## 2. 月次報告・半期評価\n\n{lines}")

    if "summary" in data:
        s = data["summary"]
        sections.append(
            "## 3. 記録量\n\n"
            f"- 記録日数: {s['record_days']}日\n"
            f"- 最長連続記録日数: {s['max_streak_days']}日"
        )

    if "daily_records" in data:
        rows = "\n".join(f"| {r['date']} | {r['body']} |" for r in data["daily_records"])
        sections.append(f"## 4. 付録：日別の業務記録\n\n| 日付 | 業務内容 |\n| --- | --- |\n{rows}")

    title = data.get("work_assignment", {}).get("name") or "ナレッジエクスポート"
    return f"# {title}\n\n" + "\n\n".join(sections)


def render_markdown(
    data: dict, selection: ExportSelection, category: GoalCategory = GoalCategory.EXAM
) -> str:
    """データ構造編7.2のMarkdown構成に沿って本文を生成する。"""
    if category == GoalCategory.READING:
        return _render_reading_markdown(data)
    if category == GoalCategory.WORK:
        return _render_work_markdown(data)

    sections: list[str] = []

    if "goal" in data:
        goal_data = data["goal"]
        subjects_text = (
            "\n".join(
                f"- {s['name']}（受験日: {s['exam_date']}、合格基準: {_format_passing_score(s)}）"
                for s in data.get("subjects", [])
            )
            or "（試験科目未登録）"
        )
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
        sections.append("## 9. 受験結果\n\n| 科目 | 合否 | 得点 |\n| --- | --- | --- |\n" + rows)

    if "diaries" in data:
        lines = "\n\n".join(
            f"### {d['date']}\n\n{d['body']}\n\n学んだこと: {d['learned']}" for d in data["diaries"]
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
        if goal.category == GoalCategory.WORK:
            # 仕事目標は総括レポート（EXAM/READING専用）を持たないため、既存の
            # goal_retrospective（period_type問わず、非匿名化版）それぞれについて
            # 匿名化版を再生成する（データ構造編7.1「仕事目標の場合」、要件定義書R-81）。
            existing = _build_work_retrospectives(session, goal, anonymized=False)
            export_progress.start(goal.id, total=len(existing) or 1)
            try:
                for row in existing:
                    if row["period_type"] == RetrospectivePeriodType.MONTHLY.value:
                        work_report_service.generate_monthly_report(
                            session, goal, period_key=row["period_key"], today=today, anonymize=True
                        )
                    else:
                        work_report_service.generate_semiannual_review(
                            session, goal, period_key=row["period_key"], today=today, anonymize=True
                        )
                    export_progress.advance(goal.id)
            finally:
                export_progress.finish(goal.id)
        else:
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
    markdown = render_markdown(data, selection, goal.category)
    content = ExportContent(data=data, markdown=markdown)
    markdown_path, json_path = write_export_files(goal, content)
    return ExportContent(
        data=data, markdown=markdown, markdown_path=markdown_path, json_path=json_path
    )
