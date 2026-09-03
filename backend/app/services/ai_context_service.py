"""AIプロンプトへ注入する変数の組み立て（設計書 ロジック・プロンプト編17.2〜17.4）。

どの値をプロンプトへ渡すかは業務判断であり、ai/パッケージの責務外（データ構造編8.1
「ai: 禁止事項=業務判断」）のためservices層に置く。既存のPhase2〜4サービス
（goal_service・cycle_service・quota_service・speed_service・slot_service・
metrics_service・material_service）を組み合わせるのみで、算出ロジック自体は再実装しない
（CLAUDE.md DRYの原則）。
"""

import datetime as dt
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai.prompt_builder import MaterialStatusEntry
from app.constants.enums import (
    BaselineReason,
    DayType,
    ExamResultType,
    GoalStatus,
    Granularity,
    RecordState,
)
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyGoalDiary, DailyRecord, StudyLog, WeeklySummary
from app.services import (
    baseline_service,
    calendar_service,
    cycle_service,
    goal_service,
    material_service,
    metrics_service,
    quota_service,
    speed_service,
)
from app.services import slot_service as slot_service_module
from app.services.record_service import DiaryEntryItem, StudyLogItem

#: 総括レポート向けの月次集約粒度（ロジック・プロンプト編17.5「{{quality_trend}}:
#: 品質指標の推移（周回別、月次集約）」）。
_RETROSPECTIVE_QUALITY_GRANULARITY = Granularity.MONTH

#: リプラン契機の日本語表記（AIプロンプト向け生成テキスト。frontendのja.jsonとは別。
#: バックエンドのAIプロンプトは常に日本語のため、UI表示ロケールとは独立して定義する）。
_BASELINE_REASON_LABELS = {
    BaselineReason.INITIAL: "初期設定",
    BaselineReason.REPLAN: "リプラン",
    BaselineReason.EXAM_DATE_FIXED: "受験日確定",
    BaselineReason.MATERIAL_CHANGED: "教材変更",
    BaselineReason.CYCLE_CHANGED: "周回数変更",
}

_EXAM_RESULT_LABELS = {
    ExamResultType.PASS: "合格",
    ExamResultType.FAIL: "不合格",
    ExamResultType.PENDING: "未判定",
}


def list_active_goals(session: Session) -> list[Goal]:
    """進行中（ACTIVE）の目標一覧を取得する。"""
    return session.query(Goal).filter(Goal.status == GoalStatus.ACTIVE).order_by(Goal.id).all()


def list_active_materials(goals: list[Goal]) -> list[Material]:
    """指定した目標群に属する有効な教材一覧を取得する。"""
    return [material for goal in goals for material in goal.materials if material.is_active]


def _group_materials_by_goal(materials: list[Material]) -> dict[int, list[Material]]:
    """教材を所属goal_idごとにグルーピングする（build_material_status_entries・
    build_slot_summaryで共通利用、DRYの原則）。"""
    by_goal: dict[int, list[Material]] = defaultdict(list)
    for material in materials:
        by_goal[material.goal_id].append(material)
    return by_goal


def build_diary_text(entries: list[DiaryEntryItem], goals: list[Goal]) -> tuple[str, str]:
    """{{diary_body}}/{{diary_learned}}: 複数目標分の日記エントリを1本の文字列に整形する
    （17.2）。内容のある目標が2件以上のときのみ`■ 目標名`見出しを付けて結合し、1件のみ
    なら見出しなしでそのまま返す（既存の単一目標運用時のプロンプト出力を変えない）。
    """
    goal_names = {goal.id: goal.name for goal in goals}

    def join_texts(texts: list[tuple[int, str]]) -> str:
        non_empty = [(goal_id, text) for goal_id, text in texts if text]
        if not non_empty:
            return ""
        if len(non_empty) == 1:
            return non_empty[0][1]
        return "\n\n".join(
            f"■ {goal_names.get(goal_id, '')}\n{text}" for goal_id, text in non_empty
        )

    diary_body = join_texts([(entry.goal_id, entry.diary_body) for entry in entries])
    diary_learned = join_texts([(entry.goal_id, entry.diary_learned) for entry in entries])
    return diary_body, diary_learned


def _format_days_remaining(today: dt.date, target: dt.date) -> str:
    days = (target - today).days
    if days >= 0:
        return f"残り{days}日"
    return f"{-days}日超過"


def build_goal_summary(goals: list[Goal], today: dt.date) -> str:
    """{{goal_summary}}: 目標名、科目構成、各科目の受験日、残日数（17.2）。"""
    if not goals:
        return "（進行中の目標はありません）"
    lines: list[str] = []
    for goal in goals:
        lines.append(f"■ {goal.name}")
        subjects = sorted(goal.exam_subjects, key=lambda s: s.display_order)
        if not subjects:
            lines.append("  （試験科目未登録）")
            continue
        for subject in subjects:
            exam_date = material_service.effective_exam_date(subject)
            lines.append(
                f"  ・{subject.name}：受験日 {exam_date.isoformat()}"
                f"（{_format_days_remaining(today, exam_date)}）"
            )
    return "\n".join(lines)


def build_material_status_entries(
    session: Session,
    materials: list[Material],
    today: dt.date,
    treat_holiday_as_buffer: bool,
) -> list[MaterialStatusEntry]:
    """{{material_status}}: 教材ごとの総量・予定周回・現在周回・残量・締切・日次ノルマ・
    必要速度・実効速度・完了予測日・乖離日数（17.2）。
    """
    by_goal = _group_materials_by_goal(materials)

    entries: list[MaterialStatusEntry] = []
    for goal_materials in by_goal.values():
        goal = goal_materials[0].goal
        contention = [m for m in goal.materials if m.is_active]
        for material in goal_materials:
            progress = cycle_service.get_material_progress(session, material)
            quota = quota_service.compute_material_quota(
                session, goal, material, today, treat_holiday_as_buffer
            )
            required_speed = speed_service.compute_required_speed(
                session, goal, material, contention, today, treat_holiday_as_buffer
            )
            effective_speed = speed_service.compute_effective_speed(
                session, material, progress.current_cycle
            )
            forecast = speed_service.compute_forecast_date(
                session, goal, material, contention, today, treat_holiday_as_buffer
            )
            required_speed_text = (
                f"{required_speed:.2f}{material.unit_label}/時間"
                if required_speed is not None
                else "算出不可"
            )
            effective_speed_text = (
                f"{effective_speed.speed:.2f}{material.unit_label}/時間"
                if effective_speed is not None
                else "算出不可"
            )
            if forecast.forecast_date is not None:
                # ForecastResultはforecast_dateとoverrun_daysを常にセットで設定する
                # （speed_service.compute_forecast_date）ため、ここでoverrun_daysの
                # None判定は不要。
                forecast_text = (
                    f"完了予測日 {forecast.forecast_date.isoformat()}"
                    f"（乖離 {forecast.overrun_days}日）"
                )
            else:
                forecast_text = "完了予測日 算出不可"
            text = (
                f"■ {material.name}（{goal.name}）\n"
                f"  総量 {material.total_amount}{material.unit_label} ×"
                f" {material.planned_cycles}周、現在{progress.current_cycle}周目、"
                f"残量 {progress.remaining:.1f}{material.unit_label}、"
                f"締切 {material.due_date.isoformat()}\n"
                f"  日次ノルマ {quota:.1f}{material.unit_label}/日、"
                f"必要速度 {required_speed_text}、実効速度 {effective_speed_text}、"
                f"{forecast_text}"
            )
            entries.append(MaterialStatusEntry(due_date=material.due_date, text=text))
    return entries


def build_slot_summary(
    session: Session, materials: list[Material], today: dt.date
) -> str:
    """{{slot_summary}}: 本日利用可能なスロットと教材への割当（17.2）。"""
    slots_by_weekday = slot_service_module.group_slots_by_weekday(
        slot_service_module.get_active_slots(session)
    )
    total_hours = slot_service_module.compute_total_hours_for_date(slots_by_weekday, today)
    if total_hours <= 0:
        return "（本日利用可能なスロットはありません）"

    lines = [f"本日の総利用可能時間: {total_hours:.1f}時間"]
    by_goal = _group_materials_by_goal(materials)

    for goal_materials in by_goal.values():
        goal = goal_materials[0].goal
        weights = speed_service.compute_weights(session, goal_materials)
        allocation = slot_service_module.allocate_day(
            weights, slots_by_weekday, today, goal.resource_ratio
        )
        for material in goal_materials:
            hours = allocation.get(material.id, 0.0)
            if hours > 0:
                lines.append(f"  ・{material.name}: {hours:.2f}時間")
    return "\n".join(lines)


def build_buffer_usage_rate_text(
    session: Session, goals: list[Goal], today: dt.date, treat_holiday_as_buffer: bool
) -> str:
    """{{buffer_usage_rate}}: バッファ日の消費状況（17.2、13.1）。"""
    if not goals:
        return "（進行中の目標はありません）"
    lines = []
    for goal in goals:
        rate = metrics_service.compute_buffer_usage_rate(
            session, goal, today, treat_holiday_as_buffer
        )
        rate_text = f"{rate:.0%}" if rate is not None else "算出不可（経過バッファ日なし）"
        lines.append(f"{goal.name}: {rate_text}")
    return "\n".join(lines)


def build_today_logs_text(items: list[StudyLogItem], materials_by_id: dict[int, Material]) -> str:
    """{{today_logs}}: 本日の教材別実績（投下時間、完了分量、周回、品質指標、17.2）。"""
    if not items:
        return "（本日の実績入力はまだありません）"
    lines = []
    for item in items:
        material = materials_by_id[item.material_id]
        minutes_text = f"{item.minutes_spent}分" if item.minutes_spent else "時間未入力"
        cycle_text = f"{item.cycle_number}周目" if item.cycle_number is not None else "周回未指定"
        quality_text = f"、品質指標 {item.quality_value}" if item.quality_value is not None else ""
        lines.append(
            f"・{material.name}: {item.amount_completed}{material.unit_label}"
            f"（{minutes_text}、{cycle_text}{quality_text}）"
        )
    return "\n".join(lines)


def build_progress_summary(
    session: Session, materials: list[Material]
) -> str:
    """{{progress_summary}}: 教材ごとの進捗率と現在周回（17.4）。"""
    if not materials:
        return "（対象教材はありません）"
    lines = []
    for material in materials:
        progress = cycle_service.get_material_progress(session, material)
        rate = metrics_service.compute_progress_rate(progress)
        lines.append(
            f"・{material.name}: {rate:.0%}（現在{progress.current_cycle}周目）"
        )
    return "\n".join(lines)


def build_recent_activity_text(
    session: Session, goals: list[Goal], today: dt.date, lookback_days: int = 7
) -> str:
    """{{recent_activity}}: 直近N日間の報告状況と実績（17.4、既定7日）。

    渡された目標群の教材に紐づくstudy_logのみを集計する（他目標の実績が混入しないよう
    study_log.material_idで絞り込む、未決事項L-04関連。「今日の一言」を目標ごとに独立
    生成する際、他目標の活動量が混ざらないようにするために必須）。
    """
    if not goals:
        return "（進行中の目標はありません）"
    material_ids = [material.id for goal in goals for material in goal.materials]
    if not material_ids:
        return "（対象教材はありません）"
    period_start = today - dt.timedelta(days=lookback_days - 1)
    rows = (
        session.query(
            DailyRecord.record_date, DailyRecord.record_state, StudyLog.amount_completed
        )
        .join(StudyLog, StudyLog.daily_record_id == DailyRecord.id)
        .filter(
            StudyLog.material_id.in_(material_ids),
            DailyRecord.record_date >= period_start,
            DailyRecord.record_date <= today,
        )
        .all()
    )
    if not rows:
        return "（直近の実績はありません）"
    totals: dict[tuple[dt.date, RecordState], float] = defaultdict(float)
    for record_date, record_state, amount in rows:
        totals[(record_date, record_state)] += amount
    lines = [
        f"・{record_date.isoformat()}: "
        f"{'報告済み' if record_state == RecordState.REPORTED else '進捗のみ'}、"
        f"完了量計 {amount}"
        for (record_date, record_state), amount in sorted(totals.items())
    ]
    return "\n".join(lines)


def build_recent_weekly_summaries(
    session: Session, goals: list[Goal], inject_weeks: int
) -> list[str]:
    """{{weekly_summaries}}: 直近の週次要約を新しい順に（17.2、15.3）。"""
    if not goals:
        return []
    goal_names = {goal.id: goal.name for goal in goals}
    rows = (
        session.query(WeeklySummary)
        .filter(WeeklySummary.goal_id.in_(goal_names), WeeklySummary.is_anonymized.is_(False))
        .order_by(WeeklySummary.week_start_date.desc())
        .limit(inject_weeks)
        .all()
    )
    return [
        f"[{row.week_start_date.isoformat()}〜{row.week_end_date.isoformat()} "
        f"{goal_names[row.goal_id]}]\n{row.summary_body}"
        for row in rows
    ]


def build_week_logs_text(
    session: Session, goal: Goal, week_start: dt.date, week_end: dt.date
) -> str:
    """{{week_logs}}: 週内の日別実績（周回を含む、17.3）。"""
    material_ids = [material.id for material in goal.materials]
    if not material_ids:
        return "（対象教材はありません）"
    rows = (
        session.query(
            DailyRecord.record_date,
            StudyLog.material_id,
            StudyLog.amount_completed,
            StudyLog.cycle_number,
            StudyLog.minutes_spent,
        )
        .join(StudyLog, StudyLog.daily_record_id == DailyRecord.id)
        .filter(
            StudyLog.material_id.in_(material_ids),
            DailyRecord.record_date >= week_start,
            DailyRecord.record_date <= week_end,
        )
        .order_by(DailyRecord.record_date)
        .all()
    )
    if not rows:
        return "（この週の実績はありません）"
    material_names = {material.id: material.name for material in goal.materials}
    lines = []
    for record_date, material_id, amount, cycle_number, minutes in rows:
        minutes_text = f"{minutes}分" if minutes else "時間未入力"
        lines.append(
            f"・{record_date.isoformat()} {material_names[material_id]}: {amount}"
            f"（{cycle_number}周目、{minutes_text}）"
        )
    return "\n".join(lines)


def build_week_diaries_text(
    session: Session, goal: Goal, week_start: dt.date, week_end: dt.date
) -> str:
    """{{week_diaries}}: 週内の日記（行動・所感、学んだこと、17.3）。

    日記は目標別（DailyGoalDiary）に保持しているため、goal_idで絞り込む
    （複数目標が同時進行していた週に他目標の日記が混入しないようにする、L-04関連）。
    """
    rows = (
        session.query(
            DailyRecord.record_date, DailyGoalDiary.diary_body, DailyGoalDiary.diary_learned
        )
        .join(DailyGoalDiary, DailyGoalDiary.daily_record_id == DailyRecord.id)
        .filter(
            DailyGoalDiary.goal_id == goal.id,
            DailyRecord.record_date >= week_start,
            DailyRecord.record_date <= week_end,
            DailyRecord.record_state == RecordState.REPORTED,
        )
        .order_by(DailyRecord.record_date)
        .all()
    )
    if not rows:
        return "（この週の日記はありません）"
    return "\n\n".join(
        f"【{record_date.isoformat()}】\n"
        f"行動・所感: {diary_body or ''}\n"
        f"学んだこと: {diary_learned or ''}"
        for record_date, diary_body, diary_learned in rows
    )


def build_week_metrics_text(
    session: Session,
    goal: Goal,
    week_start: dt.date,
    week_end: dt.date,
    treat_holiday_as_buffer: bool,
) -> str:
    """{{week_metrics}}: 週の集計値（総投下時間、総完了量、品質指標平均、報告日数、
    バッファ消費、17.3）。
    """
    material_ids = [material.id for material in goal.materials]
    rows = (
        session.query(StudyLog.amount_completed, StudyLog.minutes_spent, StudyLog.quality_value)
        .join(DailyRecord, StudyLog.daily_record_id == DailyRecord.id)
        .filter(
            StudyLog.material_id.in_(material_ids),
            DailyRecord.record_date >= week_start,
            DailyRecord.record_date <= week_end,
        )
        .all()
        if material_ids
        else []
    )
    total_amount = sum(row.amount_completed for row in rows)
    total_minutes = sum(row.minutes_spent or 0 for row in rows)
    qualities = [row.quality_value for row in rows if row.quality_value is not None]
    avg_quality_text = f"{sum(qualities) / len(qualities):.1f}" if qualities else "データなし"

    reported_days = (
        session.query(DailyRecord.id)
        .filter(
            DailyRecord.record_date >= week_start,
            DailyRecord.record_date <= week_end,
            DailyRecord.record_state == RecordState.REPORTED,
        )
        .count()
    )

    day_types = calendar_service.resolve_day_types(
        session, week_start, week_end, treat_holiday_as_buffer
    )
    buffer_days = [d for d, day_type in day_types.items() if day_type == DayType.BUFFER]
    dates_with_log = (
        {
            row[0]
            for row in session.query(DailyRecord.record_date)
            .join(StudyLog, StudyLog.daily_record_id == DailyRecord.id)
            .filter(DailyRecord.record_date.in_(buffer_days))
            .distinct()
        }
        if buffer_days
        else set()
    )
    buffer_rate_text = (
        f"{len(dates_with_log) / len(buffer_days):.0%}" if buffer_days else "算出不可"
    )

    return (
        f"総投下時間: {total_minutes / 60:.1f}時間\n"
        f"総完了量: {total_amount}\n"
        f"品質指標平均: {avg_quality_text}\n"
        f"報告日数: {reported_days}日\n"
        f"バッファ消費率: {buffer_rate_text}"
    )


# --- 総括レポート（GOAL_RETROSPECTIVE、17.5、実装フェーズ分割計画書Phase10） ---


def build_material_summary_text(session: Session, materials: list[Material]) -> str:
    """{{material_summary}}: 教材ごとの総量・予定周回・実績周回・投下時間（17.5）。"""
    if not materials:
        return "（対象教材はありません）"
    lines = []
    for material in materials:
        progress = cycle_service.get_material_progress(session, material)
        completed_cycles = cycle_service.compute_completed_cycles(material, progress)
        total_minutes = (
            session.query(func.sum(StudyLog.minutes_spent))
            .filter(StudyLog.material_id == material.id)
            .scalar()
            or 0
        )
        lines.append(
            f"・{material.name}: 総量 {material.total_amount}{material.unit_label} ×"
            f" {material.planned_cycles}周、実績 {completed_cycles}周完了、"
            f"投下時間 {total_minutes / 60:.1f}時間"
        )
    return "\n".join(lines)


def build_overall_metrics_text(
    session: Session, goal: Goal, today: dt.date, treat_holiday_as_buffer: bool
) -> str:
    """{{overall_metrics}}: 総投下時間、学習日数、報告率、バッファ消費率、リプラン回数（17.5）。"""
    material_ids = [material.id for material in goal.materials]
    study_summary = metrics_service.compute_study_summary(session, material_ids)
    total_minutes = study_summary.total_minutes
    study_days = study_summary.study_days
    report_rate = metrics_service.compute_report_rate(session, goal, today)
    buffer_usage_rate = metrics_service.compute_buffer_usage_rate(
        session, goal, today, treat_holiday_as_buffer
    )
    buffer_usage_text = (
        f"{buffer_usage_rate:.0%}" if buffer_usage_rate is not None else "算出不可"
    )
    replan_count = metrics_service.compute_replan_count(session, goal)
    return (
        f"総投下時間: {total_minutes / 60:.1f}時間\n"
        f"学習日数: {study_days}日\n"
        f"報告率: {report_rate:.0%}\n"
        f"バッファ消費率: {buffer_usage_text}\n"
        f"リプラン回数: {replan_count}回"
    )


def build_quality_trend_text(session: Session, materials: list[Material]) -> str:
    """{{quality_trend}}: 品質指標の推移（周回別、月次集約、17.5）。"""
    if not materials:
        return "（対象教材はありません）"
    lines = []
    for material in materials:
        trend = metrics_service.compute_quality_trend(
            session, material.id, _RETROSPECTIVE_QUALITY_GRANULARITY
        )
        if not trend:
            continue
        lines.append(f"■ {material.name}")
        for cycle_number in sorted(trend):
            points_text = "、".join(
                f"{point.period_start.isoformat()}: {point.value:.1f}"
                for point in trend[cycle_number]
            )
            lines.append(f"  {cycle_number}周目: {points_text}")
    return "\n".join(lines) if lines else "（品質指標の記録はありません）"


def build_replan_history_text(session: Session, goal: Goal) -> str:
    """{{replan_history}}: リプラン履歴（日付、契機、変更前後のノルマ、
    その時点の残量と残日数、17.5）。"""
    baselines = goal_service.get_baselines(session, goal)
    changes = baseline_service.compute_baseline_changes(baselines)
    if not changes:
        return "（計画基準値の記録はありません）"
    material_names = {material.id: material.name for material in goal.materials}
    lines = []
    for change in changes:
        reason_text = _BASELINE_REASON_LABELS[change.reason]
        quota_text = (
            f"{change.quota_before:.1f}→{change.quota_after:.1f}"
            if change.quota_before is not None
            else f"{change.quota_after:.1f}（初期値）"
        )
        lines.append(
            f"・{change.effective_from.isoformat()} {material_names.get(change.material_id, '')}"
            f"（{reason_text}）: ノルマ {quota_text}、"
            f"残量 {change.remaining_at_baseline:.1f}、残り{change.plan_days_at_baseline}日"
        )
    return "\n".join(lines)


def build_exam_results_text(goal: Goal) -> str:
    """{{exam_results}}: 科目ごとの合否と得点（17.5）。"""
    if not goal.exam_subjects:
        return "（試験科目未登録）"
    lines = []
    for subject in sorted(goal.exam_subjects, key=lambda s: s.display_order):
        result = subject.exam_result
        if result is None:
            lines.append(f"・{subject.name}: 未登録")
            continue
        score_text = f"、得点 {result.score}" if result.score is not None else ""
        lines.append(
            f"・{subject.name}: {_EXAM_RESULT_LABELS[result.result]}{score_text}"
            f"（受験日 {result.taken_date.isoformat()}）"
        )
    return "\n".join(lines)


def build_all_weekly_summaries_text(session: Session, goal: Goal) -> str:
    """{{weekly_summaries}}（総括レポート向け）: 全週の要約を時系列順に（17.5「全週の要約」。
    build_recent_weekly_summariesは日次報告向けに直近N週へ絞る別用途のため分離する）。
    """
    rows = (
        session.query(WeeklySummary)
        .filter(WeeklySummary.goal_id == goal.id, WeeklySummary.is_anonymized.is_(False))
        .order_by(WeeklySummary.week_start_date)
        .all()
    )
    if not rows:
        return "（週次要約はありません）"
    return "\n\n".join(
        f"[{row.week_start_date.isoformat()}〜{row.week_end_date.isoformat()}]\n{row.summary_body}"
        for row in rows
    )


def build_anonymize_instruction(anonymize: bool) -> str:
    """{{anonymize}}: 匿名化の指示（匿名化版生成時のみ、17.5、データ構造編7.3）。"""
    if not anonymize:
        return ""
    return (
        "# 匿名化の指示\n"
        "業務・家庭など個人や勤務先を特定しうる固有の事情への言及を避け、"
        "一般化して記述してください。"
    )
