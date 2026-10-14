"""ナレッジエクスポートのうち資格試験（EXAM）固有の処理（設計書データ構造編7章、
仕様書6.10 SC-13）。共通処理は`export_service_common.py`を参照（実装フェーズ分割計画書
S02、`export_service.py`からの分割）。
"""

import datetime as dt
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.constants.enums import AiPurpose, ChatRole, Granularity, PassingScoreType, RecordState
from app.constants.export_markdown import (
    EXPORT_DEFAULT_TITLE,
    EXPORT_HEADING_AI_DIALOGUE,
    EXPORT_HEADING_APPENDIX_DAILY_RECORDS,
    EXPORT_HEADING_DIARIES,
    EXPORT_HEADING_EXAM_RESULTS,
    EXPORT_HEADING_MATERIALS,
    EXPORT_HEADING_OVERVIEW,
    EXPORT_HEADING_QUALITY_TREND,
    EXPORT_HEADING_RECAP_THEMES,
    EXPORT_HEADING_REPLAN_HISTORY,
    EXPORT_HEADING_RETROSPECTIVE,
    EXPORT_HEADING_STUDY_VOLUME,
    EXPORT_HEADING_WEEKLY_SUMMARIES,
    EXPORT_LABEL_AVERAGE_TIME,
    EXPORT_LABEL_EXAM_DATE_PREFIX,
    EXPORT_LABEL_EXAM_NAME,
    EXPORT_LABEL_LEARNED,
    EXPORT_LABEL_PASSING_SCORE_PREFIX,
    EXPORT_LABEL_REPORT_RATE,
    EXPORT_LABEL_STATUS,
    EXPORT_LABEL_STUDY_DAYS,
    EXPORT_LABEL_STUDY_PERIOD,
    EXPORT_LABEL_TOTAL_TIME,
    EXPORT_PLACEHOLDER_NO_BODY,
    EXPORT_PLACEHOLDER_NO_RECORDS,
    EXPORT_PLACEHOLDER_NO_RETROSPECTIVE,
    EXPORT_PLACEHOLDER_NO_SUBJECTS,
    EXPORT_PLACEHOLDER_NOT_CLOSED,
    EXPORT_TABLE_HEAD_DAILY_RECORDS,
    EXPORT_TABLE_HEAD_EXAM_RESULTS,
    EXPORT_TABLE_HEAD_MATERIALS,
    EXPORT_TABLE_HEAD_REPLAN,
    EXPORT_UNIT_CYCLE,
    EXPORT_UNIT_DAYS,
    EXPORT_UNIT_HOURS,
    EXPORT_UNIT_MINUTES_PER_DAY,
    EXPORT_UNIT_POINTS,
)
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import (
    ChatMessage,
    DailyGoalDiary,
    DailyRecord,
    StudyLog,
    StudyLogSlotTime,
    WeeklySummary,
)
from app.models.resource import ResourceSlot
from app.services import (
    baseline_service,
    cycle_service,
    goal_service,
    material_service,
    metrics_service,
    recap_service,
    retrospective_service,
)
from app.services.export_service_common import ExportSelection

_RESULT_LABELS = {"PASS": "合格", "FAIL": "不合格", "PENDING": "未判定"}
_REASON_LABELS = {
    "INITIAL": "初期設定",
    "REPLAN": "リプラン",
    "EXAM_DATE_FIXED": "受験日確定",
    "MATERIAL_CHANGED": "教材変更",
    "CYCLE_CHANGED": "周回数変更",
}


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
        return f"{passing_score:g}/{subject_data['passing_score_max']:g}{EXPORT_UNIT_POINTS}"
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


def build_exam_export_data(
    session: Session,
    goal: Goal,
    selection: ExportSelection,
    *,
    today: dt.date,
    treat_holiday_as_buffer: bool,
    anonymized: bool,
    data: dict,
) -> dict:
    """資格試験目標（category=EXAM）向けのエクスポートデータ組み立て（build_export_dataの
    EXAM分岐を抽出。_build_reading_export_data／_build_work_export_dataと対称の形にする、
    複雑度分割S01）。"""
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
    # テーマ本文は日記・想起記録から作られるため、匿名化時は日記本文と同様に除外する。
    if selection.recap_themes and not anonymized:
        data["recap_themes"] = recap_service.goal_themes_for_export(session, goal)
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


def _render_overview_section(data: dict) -> str:
    goal_data = data["goal"]
    subjects_text = (
        "\n".join(
            f"- {s['name']}{EXPORT_LABEL_EXAM_DATE_PREFIX}{s['exam_date']}"
            f"{EXPORT_LABEL_PASSING_SCORE_PREFIX}{_format_passing_score(s)}）"
            for s in data.get("subjects", [])
        )
        or EXPORT_PLACEHOLDER_NO_SUBJECTS
    )
    closed_at_text = goal_data["closed_at"] or EXPORT_PLACEHOLDER_NOT_CLOSED
    return (
        f"{EXPORT_HEADING_OVERVIEW}\n\n"
        f"{EXPORT_LABEL_EXAM_NAME}{goal_data['name']}\n"
        f"{EXPORT_LABEL_STUDY_PERIOD}{goal_data['start_date']} 〜 {closed_at_text}\n"
        f"{EXPORT_LABEL_STATUS}{goal_data['status']}\n\n{subjects_text}"
    )


def _render_retrospective_section(data: dict) -> str:
    body = data["retrospective"] or EXPORT_PLACEHOLDER_NO_RETROSPECTIVE
    return f"{EXPORT_HEADING_RETROSPECTIVE}\n\n{body}"


def _render_study_volume_section(data: dict) -> str:
    s = data["summary"]
    return (
        f"{EXPORT_HEADING_STUDY_VOLUME}\n\n"
        f"{EXPORT_LABEL_TOTAL_TIME}{s['total_minutes'] / 60:.1f}{EXPORT_UNIT_HOURS}\n"
        f"{EXPORT_LABEL_STUDY_DAYS}{s['study_days']}{EXPORT_UNIT_DAYS}\n"
        f"{EXPORT_LABEL_REPORT_RATE}{s['report_rate']:.0%}\n"
        f"{EXPORT_LABEL_AVERAGE_TIME}{s['average_minutes_per_day']:.1f}{EXPORT_UNIT_MINUTES_PER_DAY}"
    )


def _render_materials_section(data: dict) -> str:
    rows = "\n".join(
        f"| {m['name']} | {m['total_amount']}{m['unit']} | {m['planned_cycles']} | "
        f"{m['completed_cycles']} | {m['due_date']} |"
        for m in data["materials"]
    )
    return (
        f"{EXPORT_HEADING_MATERIALS}\n\n"
        f"{EXPORT_TABLE_HEAD_MATERIALS}\n| --- | --- | --- | --- | --- |\n"
        f"{rows}"
    )


def _render_quality_trend_section(data: dict) -> str:
    lines = []
    for entry in data["quality_trend"]:
        points = "、".join(f"{p['date']}: {p['value']:.1f}" for p in entry["series"])
        lines.append(f"- {entry['material']} {entry['cycle']}{EXPORT_UNIT_CYCLE}: {points}")
    return f"{EXPORT_HEADING_QUALITY_TREND}\n\n" + (
        "\n".join(lines) or EXPORT_PLACEHOLDER_NO_RECORDS
    )


def _render_replan_history_section(data: dict) -> str:
    rows = "\n".join(
        f"| {r['date']} | {r['material']} | {_REASON_LABELS.get(r['reason'], r['reason'])} | "
        f"{r['quota_before']} → {r['quota_after']} |"
        for r in data["replan_history"]
    )
    return (
        f"{EXPORT_HEADING_REPLAN_HISTORY}\n\n"
        f"{EXPORT_TABLE_HEAD_REPLAN}\n| --- | --- | --- | --- |\n"
        f"{rows}"
    )


def _render_weekly_summaries_section(data: dict) -> str:
    lines = "\n\n".join(f"### {w['week_start']}\n\n{w['body']}" for w in data["weekly_summaries"])
    return f"{EXPORT_HEADING_WEEKLY_SUMMARIES}\n\n" + (lines or EXPORT_PLACEHOLDER_NO_RECORDS)


def _render_recap_themes_section(data: dict) -> str:
    blocks = "\n\n".join(
        f"### {theme['name']}\n\n{theme['body'] or EXPORT_PLACEHOLDER_NO_BODY}"
        for theme in data["recap_themes"]
    )
    return f"{EXPORT_HEADING_RECAP_THEMES}\n\n" + (blocks or EXPORT_PLACEHOLDER_NO_RECORDS)


def _render_daily_records_section(data: dict) -> str:
    rows = "\n".join(
        f"| {r['date']} | {r['material']} | {r['minutes'] or '-'} | {r['amount']} | "
        f"{r['cycle']} | {r['quality'] if r['quality'] is not None else '-'} |"
        for r in data["daily_records"]
    )
    return (
        f"{EXPORT_HEADING_APPENDIX_DAILY_RECORDS}\n\n"
        f"{EXPORT_TABLE_HEAD_DAILY_RECORDS}\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"{rows}"
    )


def _render_exam_results_section(data: dict) -> str:
    rows = "\n".join(
        f"| {r['subject']} | {_RESULT_LABELS.get(r['result'], r['result'])} | "
        f"{r['score'] if r['score'] is not None else '-'} |"
        for r in data["results"]
    )
    return (
        f"{EXPORT_HEADING_EXAM_RESULTS}\n\n"
        f"{EXPORT_TABLE_HEAD_EXAM_RESULTS}\n| --- | --- | --- |\n" + rows
    )


def _render_diaries_section(data: dict) -> str:
    lines = "\n\n".join(
        f"### {d['date']}\n\n{d['body']}\n\n{EXPORT_LABEL_LEARNED}{d['learned']}"
        for d in data["diaries"]
    )
    return f"{EXPORT_HEADING_DIARIES}\n\n" + (lines or EXPORT_PLACEHOLDER_NO_RECORDS)


def _render_ai_dialogue_section(data: dict) -> str:
    lines = "\n".join(f"- [{d['date']}] {d['role']}: {d['content']}" for d in data["ai_dialogue"])
    return f"{EXPORT_HEADING_AI_DIALOGUE}\n\n" + (lines or EXPORT_PLACEHOLDER_NO_RECORDS)


#: データのキーと、対応する描画関数の対応（_render_exam_markdownの複雑度分割、S01）。
#: 1キー＝1セクションの単純な対応のため、辞書で宣言的に表現しif分岐を減らす。
_EXAM_SECTION_RENDERERS: list[tuple[str, Callable[[dict], str]]] = [
    ("goal", _render_overview_section),
    ("retrospective", _render_retrospective_section),
    ("summary", _render_study_volume_section),
    ("materials", _render_materials_section),
    ("quality_trend", _render_quality_trend_section),
    ("replan_history", _render_replan_history_section),
    ("weekly_summaries", _render_weekly_summaries_section),
    ("recap_themes", _render_recap_themes_section),
    ("daily_records", _render_daily_records_section),
    ("results", _render_exam_results_section),
    ("diaries", _render_diaries_section),
    ("ai_dialogue", _render_ai_dialogue_section),
]


def render_exam_markdown(data: dict) -> str:
    """render_markdownのEXAM分岐を抽出（_render_reading_markdown／_render_work_markdownと
    対称の形にする、複雑度分割S01）。セクションごとの組み立ては各`_render_*_section`へ
    委譲し、ここではデータに存在するキーの分だけ呼び出す（宣言的な対応表で分岐を減らす）。
    """
    sections = [renderer(data) for key, renderer in _EXAM_SECTION_RENDERERS if key in data]
    title = data.get("goal", {}).get("name", EXPORT_DEFAULT_TITLE)
    return f"# {title}\n\n" + "\n\n".join(sections)
