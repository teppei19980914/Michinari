"""AIプロンプトへ注入する変数の組み立て（仕事目標、設計書 ロジック・プロンプト編
17.4・17.8〜17.10・17.12、要件定義書6.11）。共通処理は`ai_context_common.py`を参照
（実装フェーズ分割計画書S01、`ai_context_service.py`からの分割）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.ai.prompt_builder import DatedLogEntry
from app.constants.enums import (
    AiPurpose,
    ChatRole,
    GoalCategory,
    GoalStatus,
    RecordState,
    WorkMemberGender,
)
from app.models.goal import Goal
from app.models.record import ChatMessage, DailyRecord, WorkLog
from app.models.work import WorkAssignment, WorkMember
from app.services import setting_reader
from app.services.record_service import WorkLogItem


def list_active_work_goals(session: Session) -> list[Goal]:
    """進行中（ACTIVE）の仕事目標一覧を取得する（DAILY_FEEDBACK_WORK用、実装フェーズ
    分割計画書Phase22）。"""
    return (
        session.query(Goal)
        .filter(Goal.status == GoalStatus.ACTIVE, Goal.category == GoalCategory.WORK)
        .order_by(Goal.id)
        .all()
    )


def list_active_work_assignments(goals: list[Goal]) -> list[WorkAssignment]:
    """指定した仕事目標群に属する案件情報一覧を取得する（1目標1案件のため高々1件ずつ）。"""
    return [goal.work_assignment for goal in goals if goal.work_assignment is not None]


# --- 仕事日次報告フィードバック（DAILY_FEEDBACK_WORK、17.8、実装フェーズ分割計画書Phase22） ---


def build_daily_work_summary_text(work_assignments: list[WorkAssignment], today: dt.date) -> str:
    """{{work_summary}}（DAILY_FEEDBACK_WORK、17.8）: 案件名、取引先・案件の呼称、
    想定業務内容、着手日からの経過日数。"""
    if not work_assignments:
        return "（進行中の仕事目標はありません）"
    lines = []
    for work_assignment in work_assignments:
        client_text = f"（{work_assignment.client_name}）" if work_assignment.client_name else ""
        elapsed_days = (today - work_assignment.start_date).days
        lines.append(
            f"■ {work_assignment.goal.name}{client_text}\n"
            f"  想定業務内容: {work_assignment.expected_content}\n"
            f"  着手日からの経過日数: {elapsed_days}日"
        )
    return "\n".join(lines)


def build_today_work_text(
    items: list[WorkLogItem], work_assignments_by_id: dict[int, WorkAssignment]
) -> str:
    """{{today_work}}（DAILY_FEEDBACK_WORK、17.8）: 本日の業務記録本文。"""
    if not items:
        return "（本日の業務記録はまだありません）"
    lines = []
    for item in items:
        work_assignment = work_assignments_by_id[item.work_assignment_id]
        lines.append(f"■ {work_assignment.goal.name}\n{item.body}")
    return "\n\n".join(lines)


def build_recent_work_logs_entries(
    session: Session, work_assignments: list[WorkAssignment], today: dt.date, recent_days: int
) -> list[DatedLogEntry]:
    """{{recent_work_logs}}（DAILY_FEEDBACK_WORK、17.8）: 直近recent_days日分の業務記録
    （22.4）。月次報告を経由せず原文を直接注入する（読書の{{recent_recalls}}と同じ考え方）。

    対象日（today）自身は含めない。理由・窓の定義はbuild_recent_recalls_entriesと同じ
    （2026-09-15、実運用で確認・是正）。

    record_date の古い順（昇順）で返す。整形（空の場合の表示・段階的縮退）は
    prompt_builder.build_with_degradable_entries側の責務とする（CLAUDE.md DRYの原則。
    読書のbuild_recent_recalls_entriesと同じ形）。
    """
    if not work_assignments:
        return []
    work_assignment_ids = [wa.id for wa in work_assignments]
    goal_names = {wa.id: wa.goal.name for wa in work_assignments}
    period_start = today - dt.timedelta(days=recent_days)
    rows = (
        session.query(DailyRecord.record_date, WorkLog.work_assignment_id, WorkLog.body)
        .join(WorkLog, WorkLog.daily_record_id == DailyRecord.id)
        .filter(
            WorkLog.work_assignment_id.in_(work_assignment_ids),
            DailyRecord.record_date >= period_start,
            DailyRecord.record_date < today,
        )
        .order_by(DailyRecord.record_date)
        .all()
    )
    return [
        DatedLogEntry(
            record_date=record_date,
            text=f"【{record_date.isoformat()} {goal_names[work_assignment_id]}】\n{body}",
        )
        for record_date, work_assignment_id, body in rows
    ]


# --- 月次報告・半期評価（GOAL_RETROSPECTIVE_WORK_MONTHLY/SEMIANNUAL、17.9〜17.10、22章、
# --- 実装フェーズ分割計画書Phase22） ---


def build_retrospective_work_summary_text(work_assignment: WorkAssignment) -> str:
    """{{work_summary}}（GOAL_RETROSPECTIVE_WORK_MONTHLY/SEMIANNUAL、17.9〜17.10）:
    案件名、取引先・案件の呼称、想定業務内容、着手日。"""
    client_text = (
        f"、取引先・案件の呼称 {work_assignment.client_name}" if work_assignment.client_name else ""
    )
    return (
        f"{work_assignment.goal.name}{client_text}\n"
        f"想定業務内容: {work_assignment.expected_content}\n"
        f"着手日: {work_assignment.start_date.isoformat()}"
    )


def build_work_logs_entries_for_period(
    session: Session, work_assignment: WorkAssignment, date_from: dt.date, date_to: dt.date
) -> list[DatedLogEntry]:
    """{{month_logs}}／{{period_logs}}（17.9〜17.10）: 対象期間分の業務記録を record_date
    の昇順で連結したもの（22.4）。月次報告のロールアップではなく、生の日次記録を直接参照
    する（読書のgoal_retrospectiveと同じ「生ログ直接参照」方式。半期評価が月次報告を
    ロールアップしない設計の根拠）。

    整形前のlist[DatedLogEntry]を返し、空の場合の表示・段階的縮退はprompt_builder.
    build_with_degradable_entries側の責務とする（CLAUDE.md DRYの原則）。
    """
    rows = (
        session.query(DailyRecord.record_date, WorkLog.body)
        .join(WorkLog, WorkLog.daily_record_id == DailyRecord.id)
        .filter(
            WorkLog.work_assignment_id == work_assignment.id,
            DailyRecord.record_date >= date_from,
            DailyRecord.record_date <= date_to,
        )
        .order_by(DailyRecord.record_date)
        .all()
    )
    return [
        DatedLogEntry(record_date=record_date, text=f"【{record_date.isoformat()}】\n{body}")
        for record_date, body in rows
    ]


# --- 仕事用週次要約（WEEKLY_SUMMARY_WORK、17.12、L-11） ---


def build_week_work_logs_text(
    session: Session, work_assignment: WorkAssignment, week_start: dt.date, week_end: dt.date
) -> str:
    """{{week_logs}}（WEEKLY_SUMMARY_WORK、17.12）: 週内の業務記録を record_date の
    昇順で連結したもの。仕事は実績・日記の区別を持たないため（17.8参照）、読書の
    build_week_recalls_text（17.11）と同じ考え方で1変数に統合する。
    """
    rows = (
        session.query(DailyRecord.record_date, WorkLog.body)
        .join(WorkLog, WorkLog.daily_record_id == DailyRecord.id)
        .filter(
            WorkLog.work_assignment_id == work_assignment.id,
            DailyRecord.record_date >= week_start,
            DailyRecord.record_date <= week_end,
        )
        .order_by(DailyRecord.record_date)
        .all()
    )
    if not rows:
        return "（この週の業務記録はありません）"
    return "\n\n".join(f"【{record_date.isoformat()}】\n{body}" for record_date, body in rows)


# --- 今日の一言（DAILY_MESSAGE）のWORK対応（17.4、実装フェーズ分割計画書Phase22） ---
# READINGは今日の一言の対象外のまま（要件定義書6.10）だが、WORKは要件定義書R-77により
# 対象に含める。goal_summary/progress_summary/recent_activityはEXAM専用の実装を流用できない
# （試験科目・教材を前提とするため）ため、WORK用の変数ビルダーを別途用意する。


def build_work_progress_summary(
    session: Session, work_assignments: list[WorkAssignment], today: dt.date
) -> str:
    """{{progress_summary}}のWORK版: 案件ごとの経過日数・直近記録日・連続記録日数・
    直近の月次報告有無（22.1・22.2）。build_progress_summary（EXAM用）と同じ役割。

    直近の月次報告有無を含めるのは、未生成の期に「今日の一言」から月次報告の作成を
    促せるようにするため（22.1「WORK用の変数は…直近の月次報告有無を用いて組み立てる」）。
    """
    from app.services import work_service  # 循環importを避けるため関数内でimportする

    if not work_assignments:
        return "（対象案件はありません）"
    lines = []
    for work_assignment in work_assignments:
        progress = work_service.get_work_assignment_progress(session, work_assignment, today)
        last_work_text = (
            progress.last_work_date.isoformat() if progress.last_work_date is not None else "なし"
        )
        monthly_report_text = (
            "直近の月次報告あり" if progress.has_recent_monthly_report else "直近の月次報告なし"
        )
        lines.append(
            f"・{work_assignment.goal.name}: 経過{progress.elapsed_days}日"
            f"（連続記録{progress.current_streak}日、直近記録日 {last_work_text}、"
            f"{monthly_report_text}）"
        )
    return "\n".join(lines)


def build_work_recent_activity_text(
    session: Session, work_assignments: list[WorkAssignment], today: dt.date, lookback_days: int = 7
) -> str:
    """{{recent_activity}}のWORK版: 直近lookback_days日間の業務記録件数（17.4、既定7日）。
    build_recent_activity_text（EXAM用）と同じ役割。他目標の実績が混入しないよう
    work_assignment_idで絞り込む（未決事項L-04関連）。"""
    if not work_assignments:
        return "（対象案件はありません）"
    work_assignment_ids = [wa.id for wa in work_assignments]
    period_start = today - dt.timedelta(days=lookback_days - 1)
    rows = (
        session.query(DailyRecord.record_date, DailyRecord.work_record_state)
        .join(WorkLog, WorkLog.daily_record_id == DailyRecord.id)
        .filter(
            WorkLog.work_assignment_id.in_(work_assignment_ids),
            DailyRecord.record_date >= period_start,
            DailyRecord.record_date <= today,
        )
        .distinct()
        .all()
    )
    if not rows:
        return "（直近の業務記録はありません）"
    reported_days = sum(1 for _, state in rows if state == RecordState.REPORTED)
    return f"直近{lookback_days}日間の記録日数: {len(rows)}日（うち報告確定 {reported_days}日）"


# --- AI評価レポート（EVALUATION_REPORT_WORK、要件定義書6.11） ---

_GENDER_LABELS_JA = {
    WorkMemberGender.MALE: "男性",
    WorkMemberGender.FEMALE: "女性",
    WorkMemberGender.OTHER: "その他",
}
_GENDER_LABELS_EN = {
    WorkMemberGender.MALE: "male",
    WorkMemberGender.FEMALE: "female",
    WorkMemberGender.OTHER: "other",
}


def build_evaluation_member_summary_text(session: Session, member: WorkMember) -> str:
    """{{member_summary}}（EVALUATION_REPORT_WORK）: 評価対象メンバーの氏名・性別
    （あれば）・特徴/性格（あれば）。"""
    is_english = setting_reader.is_english_locale(session)
    gender_labels = _GENDER_LABELS_EN if is_english else _GENDER_LABELS_JA
    lines = [f"氏名: {member.name}"]
    if member.gender is not None:
        lines.append(f"性別: {gender_labels[member.gender]}")
    if member.characteristics:
        lines.append(f"特徴・性格: {member.characteristics}")
    return "\n".join(lines)


def build_evaluation_feedback_history_entries(session: Session, goal: Goal) -> list[DatedLogEntry]:
    """{{feedback_history}}（EVALUATION_REPORT_WORK）: この目標（案件）の日次報告
    フィードバック（DAILY_FEEDBACK_WORK）のうちNewtonXからの応答（role=ASSISTANT）を
    record_dateの昇順で。

    ai_log（AI通信ログ）はapp_setting.log.retention_daysで自動削除される監視用ログ
    であり、goal_idも持たないため評価レポートの入力には使えない（要件定義書6.11の
    技術検証で確認済み）。chat_messageはgoal_id列を持ち（Phase26）、retentionによる
    削除の対象でもないため、こちらを参照する。

    整形前のlist[DatedLogEntry]を返し、空の場合の表示・段階的縮退はprompt_builder.
    build_with_degradable_entries側の責務とする（CLAUDE.md DRYの原則）。
    """
    rows = (
        session.query(DailyRecord.record_date, ChatMessage.content)
        .join(ChatMessage, ChatMessage.daily_record_id == DailyRecord.id)
        .filter(
            ChatMessage.goal_id == goal.id,
            ChatMessage.purpose == AiPurpose.DAILY_FEEDBACK_WORK,
            ChatMessage.role == ChatRole.ASSISTANT,
        )
        .order_by(DailyRecord.record_date, ChatMessage.sequence)
        .all()
    )
    return [
        DatedLogEntry(record_date=record_date, text=f"【{record_date.isoformat()}】\n{content}")
        for record_date, content in rows
    ]
