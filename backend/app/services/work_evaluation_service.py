"""AI評価レポートの生成・編集・履歴取得（要件定義書6.11）。

goal_retrospective（月次報告・半期評価）とはgrainが異なる（メンバー軸）ため、新規テーブル
work_evaluation_reportを使う（models/work.pyのWorkEvaluationReportのdocstring参照）。
生成のたびに新規行を追加する履歴保持型で、月次/半期報告と同様に生成後は人がレビュー・
修正してから保存する運用のため、bodyの構造化パース（work_report_service._parse_sections
のような固定見出し分割）は行わない（次期目標への引き継ぎやスコア選択欄が無いため不要、
CLAUDE.md DRYの原則＝使わない機構は作らない）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.constants.app_setting_keys import AI_ASSISTANT_UID_EVALUATION_REPORT_WORK
from app.constants.enums import AiPurpose, ConversationScope, WorkEvaluationRole
from app.models.base import utcnow
from app.models.work import WorkAssignment, WorkEvaluationReport, WorkMember
from app.services import ai_context_service, setting_reader
from app.services.exceptions import NotFoundError, ValidationError

#: {{feedback_history}}が空（対象目標のNewtonXフィードバック履歴なし）場合の表示。
_NO_FEEDBACK_HISTORY_TEXT = "（この目標のAIフィードバック履歴はありません）"
#: {{work_logs}}が空（業務記録なし）場合の表示（work_report_service._NO_PERIOD_WORK_LOGS_TEXT
#: と同文言だが、対象期間の指定有無が異なる別用途のため定数は分離する）。
_NO_WORK_LOGS_TEXT = "（業務記録はありません）"


def _ensure_evaluator_role(work_assignment: WorkAssignment) -> None:
    if work_assignment.role != WorkEvaluationRole.EVALUATOR:
        raise ValidationError("評価者ロールの案件にのみ評価レポートを生成できます")


def _ensure_member_belongs(work_assignment: WorkAssignment, member: WorkMember) -> None:
    if member.work_assignment_id != work_assignment.id:
        raise ValidationError("指定されたメンバーはこの案件に所属していません")


def generate_evaluation_report(
    session: Session,
    work_assignment: WorkAssignment,
    *,
    member: WorkMember,
    considerations: str,
    today: dt.date,
) -> WorkEvaluationReport:
    _ensure_evaluator_role(work_assignment)
    _ensure_member_belongs(work_assignment, member)

    context = prompt_builder.DegradableFeedbackContext(
        fixed_variables={
            "member_summary": ai_context_service.build_evaluation_member_summary_text(member),
            "considerations": considerations,
        },
        stages=[
            prompt_builder.DegradableEntryStage(
                key="feedback_history",
                entries=ai_context_service.build_evaluation_feedback_history_entries(
                    session, work_assignment.goal
                ),
                empty_text=_NO_FEEDBACK_HISTORY_TEXT,
            ),
            prompt_builder.DegradableEntryStage(
                key="work_logs",
                entries=ai_context_service.build_work_logs_entries_for_period(
                    session, work_assignment, work_assignment.start_date, today
                ),
                empty_text=_NO_WORK_LOGS_TEXT,
            ),
        ],
    )

    template_body = ai_orchestration.load_template_body(session, AiPurpose.EVALUATION_REPORT_WORK)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    build_result = prompt_builder.build_with_degradable_entries(template_body, context, max_chars)

    assistant_uid = setting_reader.get_str(session, AI_ASSISTANT_UID_EVALUATION_REPORT_WORK)
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=work_assignment.goal,
        scope=ConversationScope.EVALUATION_REPORT_WORK,
        scope_key=str(member.id),
        assistant_uid=assistant_uid,
        title=f"{member.name} 評価レポート（{work_assignment.goal.name}）",
    )
    send_result = ai_orchestration.send_and_log(
        session,
        purpose=AiPurpose.EVALUATION_REPORT_WORK,
        conversation=conversation,
        prompt_text=build_result.text,
        prompt_chars=build_result.prompt_chars,
        was_truncated=build_result.was_truncated,
    )

    report = WorkEvaluationReport(
        work_assignment_id=work_assignment.id,
        member_id=member.id,
        considerations=considerations,
        body=send_result.response_text,
        generated_at=utcnow(),
    )
    session.add(report)
    session.flush()
    return report


def get_evaluation_report(session: Session, report_id: int) -> WorkEvaluationReport:
    report = session.get(WorkEvaluationReport, report_id)
    if report is None:
        raise NotFoundError("評価レポート", report_id)
    return report


def update_evaluation_report(
    session: Session, report: WorkEvaluationReport, *, body: str
) -> WorkEvaluationReport:
    """レビュー画面での人による修正を保存する（goal_retrospective.edited_atと同じ意味）。"""
    report.body = body
    report.edited_at = utcnow()
    session.flush()
    return report


def list_evaluation_reports(
    session: Session, work_assignment: WorkAssignment, *, member_id: int | None = None
) -> list[WorkEvaluationReport]:
    query = session.query(WorkEvaluationReport).filter(
        WorkEvaluationReport.work_assignment_id == work_assignment.id
    )
    if member_id is not None:
        query = query.filter(WorkEvaluationReport.member_id == member_id)
    # generated_at（Python側のutcnow()）はマイクロ秒精度だが、短時間での連続生成では
    # 同一マイクロ秒に丸まり得る（実測で確認済み）。その場合generated_at単独のORDER BYは
    # 同順位となりSQLiteのタイブレークが不定になるため、idを第2キーにして常に新しい行を
    # 先頭にする（baseline_service.list_baselinesと同じ対策パターン）。
    return query.order_by(
        WorkEvaluationReport.generated_at.desc(), WorkEvaluationReport.id.desc()
    ).all()
