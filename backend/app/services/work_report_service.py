"""月次報告・半期評価（GOAL_RETROSPECTIVE_WORK_MONTHLY／SEMIANNUAL）の生成・編集
（設計書 ロジック・プロンプト編17.9〜17.10・22.5〜22.6、データ構造編5.4、
実装フェーズ分割計画書Phase22）。

読書の読了レポート（retrospective_service.py）と異なり、クローズ時の1回きりではなく、
月次・半期という周期でgoal_retrospectiveの同一行を上書きし続ける（WORKの行は
「1期間1行」。データ構造編5.4「WORKでの流用」）。AIの役割は「達成度の判定」
「業務内容の要約」「振り返り文の生成」「次期目標案の提示」（月次のみ「報告・連絡事項の
抽出」）に絞り込み、「当期の目標」はAIに書かせずアプリケーション層が前期の
next_goal_textをそのまま複製する（17.9「AIの役割を絞り込む設計」）。
"""

import calendar as calendar_module
import datetime as dt

from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY,
    AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL,
)
from app.constants.enums import AiPurpose, ConversationScope, RetrospectivePeriodType
from app.constants.sentinels import UNSET
from app.models.base import utcnow
from app.models.goal import Goal
from app.models.retrospective import GoalRetrospective
from app.services import ai_context_service, retrospective_service, setting_reader
from app.services.exceptions import ValidationError

#: 月次報告のAI応答を分割する見出し文字列（17.9、この順序・この文字列を厳守）。
_MONTHLY_HEADINGS = (
    "## 業務内容の要約",
    "## 達成度",
    "## 達成状況の振り返り",
    "## 来月の目標",
    "## 報告・連絡事項",
)

#: 半期評価のAI応答を分割する見出し文字列（17.10、報告・連絡事項は対象外）。
_SEMIANNUAL_HEADINGS = (
    "## 業務内容の要約",
    "## 達成度",
    "## 達成状況の振り返り",
    "## 次半期の目標",
)


def _parse_sections(response_text: str, headings: tuple[str, ...]) -> dict[str, str]:
    """見出し文字列でAI応答を分割する（22.6）。見出しが検出できない項目は空文字のまま
    とする（生成自体は失敗させない。AI応答全文はai_logに残るため情報は失われない）。
    """
    positions = [
        (idx, heading) for heading in headings if (idx := response_text.find(heading)) != -1
    ]
    positions.sort()
    sections = dict.fromkeys(headings, "")
    for i, (idx, heading) in enumerate(positions):
        start = idx + len(heading)
        end = positions[i + 1][0] if i + 1 < len(positions) else len(response_text)
        sections[heading] = response_text[start:end].strip()
    return sections


def _parse_achievement_score(section_text: str) -> int | None:
    """達成度の節から半角数字1文字(1〜5)のみを許容する（17.9）。「対象外」を含め
    それ以外の内容はNULLとし、レビュー画面での人による確認・修正に委ねる。
    """
    stripped = section_text.strip()
    return int(stripped) if stripped in {"1", "2", "3", "4", "5"} else None


# --- 期間判定（22.5） ---


def current_monthly_period_key(today: dt.date) -> str:
    """対象日が属する暦月のperiod_key（"YYYY-MM"、22.5）。

    default_monthly_period_key（前月）と、work_service が「直近の月次報告有無」を
    判定する際の当月キー（22.2）の双方から使う（CLAUDE.md DRYの原則）。
    """
    return f"{today.year}-{today.month:02d}"


def default_monthly_period_key(today: dt.date) -> str:
    """月次報告のperiod_key既定値は前月（提出対象年月は常に生成月の前月）。"""
    return _previous_monthly_period_key(current_monthly_period_key(today))


def _previous_monthly_period_key(period_key: str) -> str:
    year, month = (int(part) for part in period_key.split("-"))
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def _monthly_period_range(period_key: str) -> tuple[dt.date, dt.date]:
    year, month = (int(part) for part in period_key.split("-"))
    date_from = dt.date(year, month, 1)
    last_day = calendar_module.monthrange(year, month)[1]
    return date_from, dt.date(year, month, last_day)


def _monthly_period_display(period_key: str) -> str:
    year, month = (int(part) for part in period_key.split("-"))
    return f"{year}年{month}月"


def default_semiannual_period_key(today: dt.date) -> str:
    """半期評価のperiod_key既定値はTが属する半期（H1=3〜8月、H2=9月〜翌2月）。"""
    if 3 <= today.month <= 8:
        return f"{today.year}-H1"
    if today.month >= 9:
        return f"{today.year}-H2"
    return f"{today.year - 1}-H2"


def _previous_semiannual_period_key(period_key: str) -> str:
    year_text, half = period_key.split("-")
    year = int(year_text)
    return f"{year - 1}-H2" if half == "H1" else f"{year}-H1"


def _semiannual_period_range(period_key: str) -> tuple[dt.date, dt.date]:
    year_text, half = period_key.split("-")
    year = int(year_text)
    if half == "H1":
        return dt.date(year, 3, 1), dt.date(year, 8, 31)
    next_year = year + 1
    last_day = 29 if calendar_module.isleap(next_year) else 28
    return dt.date(year, 9, 1), dt.date(next_year, 2, last_day)


def _semiannual_period_display(period_key: str) -> str:
    year_text, half = period_key.split("-")
    year = int(year_text)
    if half == "H1":
        return f"{year}年3月〜8月"
    return f"{year}年9月〜{year + 1}年2月"


# --- goal_retrospective の取得（WORKは1期間1行、データ構造編5.4） ---


def get_work_report(
    session: Session,
    goal: Goal,
    *,
    period_type: RetrospectivePeriodType,
    period_key: str,
    anonymized: bool = False,
) -> GoalRetrospective | None:
    """指定期間の月次報告・半期評価を取得する（該当行は高々1件）。

    retrospective_service.get_latest_retrospectiveのperiod_type／period_key拡張
    （データ構造編5.4）をそのまま利用する（DRYの原則、実装フェーズ分割計画書Phase22）。
    """
    return retrospective_service.get_latest_retrospective(
        session, goal, anonymized=anonymized, period_type=period_type, period_key=period_key
    )


def _ensure_work_assignment(goal: Goal) -> None:
    if goal.work_assignment is None:
        raise ValidationError("案件情報が未登録の仕事目標には月次報告・半期評価を生成できません")


# --- 本文の組み立て（22.6のMarkdownテンプレート） ---


def _render_monthly_body(
    *,
    target_month: str,
    business_summary: str,
    target_goal_text: str,
    achievement_score: int | None,
    achievement_reflection: str,
    next_goal_text: str,
    report_notes: str,
) -> str:
    score_text = str(achievement_score) if achievement_score is not None else ""
    return (
        f"# 月次報告（{target_month}）\n\n"
        f"## 業務内容（案件内容）\n{business_summary}\n\n"
        f"## 当月の目標\n{target_goal_text}\n\n"
        f"## 目標がどの程度達成されたか\n{score_text}\n\n"
        f"## 目標の達成状況と進捗に関する振り返り\n{achievement_reflection}\n\n"
        f"## 来月の目標\n{next_goal_text}\n\n"
        f"## 報告・連絡事項\n{report_notes}"
    )


def _render_semiannual_body(
    *,
    target_period: str,
    business_summary: str,
    target_goal_text: str,
    achievement_score: int | None,
    achievement_reflection: str,
    next_goal_text: str,
) -> str:
    score_text = str(achievement_score) if achievement_score is not None else ""
    return (
        f"# 半期評価（{target_period}）\n\n"
        f"## 業務内容（案件内容）\n{business_summary}\n\n"
        f"## 当該半期の目標\n{target_goal_text}\n\n"
        f"## 目標がどの程度達成されたか\n{score_text}\n\n"
        f"## 目標の達成状況と進捗に関する振り返り\n{achievement_reflection}\n\n"
        f"## 次半期の目標\n{next_goal_text}"
    )


# --- 生成（POST、既存行があれば上書き） ---


def generate_monthly_report(
    session: Session,
    goal: Goal,
    *,
    period_key: str | None,
    today: dt.date,
    anonymize: bool = False,
) -> GoalRetrospective:
    _ensure_work_assignment(goal)
    work_assignment = goal.work_assignment
    resolved_period_key = period_key or default_monthly_period_key(today)
    target_month = _monthly_period_display(resolved_period_key)
    date_from, date_to = _monthly_period_range(resolved_period_key)

    previous_row = get_work_report(
        session,
        goal,
        period_type=RetrospectivePeriodType.MONTHLY,
        period_key=_previous_monthly_period_key(resolved_period_key),
        anonymized=anonymize,
    )
    target_goal_text = (
        previous_row.next_goal_text
        if previous_row is not None and previous_row.next_goal_text
        else "（前月の記録が無いため、今回は目標との比較を行いません）"
    )

    variables = {
        "work_summary": ai_context_service.build_retrospective_work_summary_text(work_assignment),
        "target_month": target_month,
        "target_goal_text": target_goal_text,
        "month_logs": ai_context_service.build_work_logs_text_for_period(
            session, work_assignment, date_from, date_to
        ),
        "anonymize": ai_context_service.build_anonymize_instruction(anonymize),
    }

    template_body = ai_orchestration.load_template_body(
        session, AiPurpose.GOAL_RETROSPECTIVE_WORK_MONTHLY
    )
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    build_result = prompt_builder.build_simple(template_body, variables, max_chars)

    assistant_uid = setting_reader.get_str(
        session, AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_MONTHLY
    )
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=ConversationScope.GOAL_RETROSPECTIVE_WORK_MONTHLY,
        scope_key=resolved_period_key,
        assistant_uid=assistant_uid,
        title=f"{target_month} 月次報告",
    )
    send_result = ai_orchestration.send_and_log(
        session,
        purpose=AiPurpose.GOAL_RETROSPECTIVE_WORK_MONTHLY,
        conversation=conversation,
        prompt_text=build_result.text,
        prompt_chars=build_result.prompt_chars,
        was_truncated=build_result.was_truncated,
    )

    sections = _parse_sections(send_result.response_text, _MONTHLY_HEADINGS)
    business_summary = sections[_MONTHLY_HEADINGS[0]]
    achievement_score = _parse_achievement_score(sections[_MONTHLY_HEADINGS[1]])
    achievement_reflection = sections[_MONTHLY_HEADINGS[2]]
    next_goal_text = sections[_MONTHLY_HEADINGS[3]]
    report_notes = sections[_MONTHLY_HEADINGS[4]]

    retrospective = get_work_report(
        session,
        goal,
        period_type=RetrospectivePeriodType.MONTHLY,
        period_key=resolved_period_key,
        anonymized=anonymize,
    )
    if retrospective is None:
        retrospective = GoalRetrospective(
            goal_id=goal.id,
            period_type=RetrospectivePeriodType.MONTHLY,
            period_key=resolved_period_key,
            is_anonymized=anonymize,
        )
        session.add(retrospective)

    retrospective.target_goal_text = target_goal_text
    retrospective.business_summary = business_summary
    retrospective.achievement_score = achievement_score
    retrospective.achievement_reflection = achievement_reflection
    retrospective.next_goal_text = next_goal_text
    retrospective.report_notes = report_notes
    retrospective.body = _render_monthly_body(
        target_month=target_month,
        business_summary=business_summary,
        target_goal_text=target_goal_text,
        achievement_score=achievement_score,
        achievement_reflection=achievement_reflection,
        next_goal_text=next_goal_text,
        report_notes=report_notes,
    )
    retrospective.generated_at = utcnow()
    retrospective.edited_at = None
    session.flush()
    return retrospective


def generate_semiannual_review(
    session: Session,
    goal: Goal,
    *,
    period_key: str | None,
    today: dt.date,
    anonymize: bool = False,
) -> GoalRetrospective:
    _ensure_work_assignment(goal)
    work_assignment = goal.work_assignment
    resolved_period_key = period_key or default_semiannual_period_key(today)
    target_period = _semiannual_period_display(resolved_period_key)
    date_from, date_to = _semiannual_period_range(resolved_period_key)

    previous_row = get_work_report(
        session,
        goal,
        period_type=RetrospectivePeriodType.SEMI_ANNUAL,
        period_key=_previous_semiannual_period_key(resolved_period_key),
        anonymized=anonymize,
    )
    target_goal_text = (
        previous_row.next_goal_text
        if previous_row is not None and previous_row.next_goal_text
        else "（前半期の記録が無いため、今回は目標との比較を行いません）"
    )

    variables = {
        "work_summary": ai_context_service.build_retrospective_work_summary_text(work_assignment),
        "target_period": target_period,
        "target_goal_text": target_goal_text,
        "period_logs": ai_context_service.build_work_logs_text_for_period(
            session, work_assignment, date_from, date_to
        ),
        "anonymize": ai_context_service.build_anonymize_instruction(anonymize),
    }

    template_body = ai_orchestration.load_template_body(
        session, AiPurpose.GOAL_RETROSPECTIVE_WORK_SEMIANNUAL
    )
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    build_result = prompt_builder.build_simple(template_body, variables, max_chars)

    assistant_uid = setting_reader.get_str(
        session, AI_ASSISTANT_UID_GOAL_RETROSPECTIVE_WORK_SEMIANNUAL
    )
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=ConversationScope.GOAL_RETROSPECTIVE_WORK_SEMIANNUAL,
        scope_key=resolved_period_key,
        assistant_uid=assistant_uid,
        title=f"{target_period} 半期評価",
    )
    send_result = ai_orchestration.send_and_log(
        session,
        purpose=AiPurpose.GOAL_RETROSPECTIVE_WORK_SEMIANNUAL,
        conversation=conversation,
        prompt_text=build_result.text,
        prompt_chars=build_result.prompt_chars,
        was_truncated=build_result.was_truncated,
    )

    sections = _parse_sections(send_result.response_text, _SEMIANNUAL_HEADINGS)
    business_summary = sections[_SEMIANNUAL_HEADINGS[0]]
    achievement_score = _parse_achievement_score(sections[_SEMIANNUAL_HEADINGS[1]])
    achievement_reflection = sections[_SEMIANNUAL_HEADINGS[2]]
    next_goal_text = sections[_SEMIANNUAL_HEADINGS[3]]

    retrospective = get_work_report(
        session,
        goal,
        period_type=RetrospectivePeriodType.SEMI_ANNUAL,
        period_key=resolved_period_key,
        anonymized=anonymize,
    )
    if retrospective is None:
        retrospective = GoalRetrospective(
            goal_id=goal.id,
            period_type=RetrospectivePeriodType.SEMI_ANNUAL,
            period_key=resolved_period_key,
            is_anonymized=anonymize,
        )
        session.add(retrospective)

    retrospective.target_goal_text = target_goal_text
    retrospective.business_summary = business_summary
    retrospective.achievement_score = achievement_score
    retrospective.achievement_reflection = achievement_reflection
    retrospective.next_goal_text = next_goal_text
    retrospective.report_notes = None
    retrospective.body = _render_semiannual_body(
        target_period=target_period,
        business_summary=business_summary,
        target_goal_text=target_goal_text,
        achievement_score=achievement_score,
        achievement_reflection=achievement_reflection,
        next_goal_text=next_goal_text,
    )
    retrospective.generated_at = utcnow()
    retrospective.edited_at = None
    session.flush()
    return retrospective


# --- 編集（PATCH。行が無ければ新規作成する＝前期の記録が無い初回利用者向けの手動シード、
# --- 要件定義書R-83） ---


def update_monthly_report(
    session: Session,
    goal: Goal,
    *,
    period_key: str,
    target_goal_text: str | None = UNSET,
    business_summary: str | None = UNSET,
    achievement_score: int | None = UNSET,
    achievement_reflection: str | None = UNSET,
    next_goal_text: str | None = UNSET,
    report_notes: str | None = UNSET,
) -> GoalRetrospective:
    retrospective = get_work_report(
        session, goal, period_type=RetrospectivePeriodType.MONTHLY, period_key=period_key
    )
    if retrospective is None:
        retrospective = GoalRetrospective(
            goal_id=goal.id,
            period_type=RetrospectivePeriodType.MONTHLY,
            period_key=period_key,
            body="",
            generated_at=utcnow(),
        )
        session.add(retrospective)

    if target_goal_text is not UNSET:
        retrospective.target_goal_text = target_goal_text
    if business_summary is not UNSET:
        retrospective.business_summary = business_summary
    if achievement_score is not UNSET:
        retrospective.achievement_score = achievement_score
    if achievement_reflection is not UNSET:
        retrospective.achievement_reflection = achievement_reflection
    if next_goal_text is not UNSET:
        retrospective.next_goal_text = next_goal_text
    if report_notes is not UNSET:
        retrospective.report_notes = report_notes

    retrospective.body = _render_monthly_body(
        target_month=_monthly_period_display(period_key),
        business_summary=retrospective.business_summary or "",
        target_goal_text=retrospective.target_goal_text or "",
        achievement_score=retrospective.achievement_score,
        achievement_reflection=retrospective.achievement_reflection or "",
        next_goal_text=retrospective.next_goal_text or "",
        report_notes=retrospective.report_notes or "",
    )
    retrospective.edited_at = utcnow()
    session.flush()
    return retrospective


def update_semiannual_review(
    session: Session,
    goal: Goal,
    *,
    period_key: str,
    target_goal_text: str | None = UNSET,
    business_summary: str | None = UNSET,
    achievement_score: int | None = UNSET,
    achievement_reflection: str | None = UNSET,
    next_goal_text: str | None = UNSET,
) -> GoalRetrospective:
    retrospective = get_work_report(
        session, goal, period_type=RetrospectivePeriodType.SEMI_ANNUAL, period_key=period_key
    )
    if retrospective is None:
        retrospective = GoalRetrospective(
            goal_id=goal.id,
            period_type=RetrospectivePeriodType.SEMI_ANNUAL,
            period_key=period_key,
            body="",
            generated_at=utcnow(),
        )
        session.add(retrospective)

    if target_goal_text is not UNSET:
        retrospective.target_goal_text = target_goal_text
    if business_summary is not UNSET:
        retrospective.business_summary = business_summary
    if achievement_score is not UNSET:
        retrospective.achievement_score = achievement_score
    if achievement_reflection is not UNSET:
        retrospective.achievement_reflection = achievement_reflection
    if next_goal_text is not UNSET:
        retrospective.next_goal_text = next_goal_text

    retrospective.body = _render_semiannual_body(
        target_period=_semiannual_period_display(period_key),
        business_summary=retrospective.business_summary or "",
        target_goal_text=retrospective.target_goal_text or "",
        achievement_score=retrospective.achievement_score,
        achievement_reflection=retrospective.achievement_reflection or "",
        next_goal_text=retrospective.next_goal_text or "",
    )
    retrospective.edited_at = utcnow()
    session.flush()
    return retrospective
