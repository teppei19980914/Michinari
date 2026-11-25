"""AIによるスケジュール修正案（開発Todo_スケジュール・ガントチャート_v1.1 第13章、単位5）。

遅れの判定（AIを使わない、13.2）・目標の期限解決（D-62）・AI呼び出し（13.3）・応答の検証
（13.5）・保存と置き換え（13.6・D-65）・判断（13.7）をここへ集約する。

AI通信とトランザクション（CODING_RULES.md）：`ensure_conversation`・`send_and_log`を経由し、
AI応答を待つ間はDBへ書き込まない。修正案の保存・古い修正案の置き換えは、応答を得た後に
`serialize_writes()`内の1トランザクションでコミットする。使い捨て会話（1回ごとに完結、
会話は継続しない、13.3）のため、送信後は`discard_conversation`で後始末する
（`summary_card_service.generate_sentence`と同じ方式）。
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.ai import client as ai_client
from app.ai import conversation as ai_conversation
from app.ai import orchestration as ai_orchestration
from app.ai import prompt_builder
from app.ai.exceptions import AiAuthRequiredError
from app.constants.app_setting_keys import (
    AI_ASSISTANT_UID_SCHEDULE_REVISION,
    AI_SCHEDULE_REVISION_FOLDER_NAME,
    SCHEDULE_REVISION_DESCRIPTION_MAX_CHARS_IN_PROMPT,
    SCHEDULE_REVISION_MAX_BLOCK_CHARS,
    SCHEDULE_REVISION_REASON_MAX_CHARS,
    SCHEDULE_REVISION_RECENT_REJECTIONS_COUNT,
)
from app.constants.enums import (
    AiPurpose,
    ConversationScope,
    GoalCategory,
    GoalStatus,
    ScheduleItemStatus,
    ScheduleRevisionDecision,
    ScheduleRevisionItemKind,
    ScheduleRevisionProposalStatus,
    ScheduleRevisionTrigger,
)
from app.database import serialize_writes
from app.models.base import utcnow
from app.models.goal import Goal
from app.models.schedule import ScheduleItem
from app.models.schedule_revision import ScheduleRevisionProposal, ScheduleRevisionProposalItem
from app.schemas.schedule_revision import ScheduleRevisionDecisionInput
from app.services import (
    ai_context_common,
    ai_context_exam,
    ai_context_reading,
    ai_context_work,
    goal_service,
    material_service,
    schedule_revision_block_parsing,
    schedule_service,
    setting_reader,
)
from app.services.exceptions import (
    NotFoundError,
    ScheduleRevisionPromptTooLongError,
    ScheduleRevisionProposalNotPendingError,
    ValidationError,
)

_NO_WEEKLY_SUMMARIES_TEXT = "（まだ週次要約はありません）"
_NO_RECENT_LOGS_TEXT = "（週次要約が無い過去日の記録はありません）"
_NO_SCHEDULE_ROWS_TEXT = "（作業項目がありません）"
_NO_REJECTIONS_TEXT = "（なし）"
_NO_DEADLINE_TEXT = "なし"
_DELAY_LABEL: dict[schedule_service.ScheduleDelayKind | None, str] = {
    None: "なし",
    schedule_service.ScheduleDelayKind.END_DELAY: "終了の遅れ",
    schedule_service.ScheduleDelayKind.START_DELAY: "開始の遅れ",
}


def resolve_goal_due_date(goal: Goal) -> dt.date | None:
    """目標の期限を解決する（D-62）。既存の締切計算をそのまま使い、新しい計算式は書かない。

    資格試験：`material_service.compute_due_date`（紐づく科目の最も早い有効受験日の前日）を
    目標に紐づく全科目（`goal.exam_subjects`）・`goal.start_date`で呼ぶ。科目が1件も無い
    場合は計算できないため「期限なし」とする（単位5開発Todo2章補足1）。
    読書：`book.due_date`（NOT NULL、1目標1冊）。仕事：期限を適用しない（D-62）。
    """
    if goal.category == GoalCategory.EXAM:
        if not goal.exam_subjects:
            return None
        return material_service.compute_due_date(goal.exam_subjects, goal.start_date)
    if goal.category == GoalCategory.READING:
        return goal.book.due_date if goal.book is not None else None
    return None


def _goal_items(session: Session, goal_id: int) -> list[ScheduleItem]:
    return list(
        session.scalars(
            select(ScheduleItem)
            .where(ScheduleItem.goal_id == goal_id)
            .order_by(ScheduleItem.display_order)
        ).all()
    )


def list_revision_candidate_goal_ids(
    session: Session, category: GoalCategory, target_date: dt.date, today: dt.date
) -> list[int]:
    """確定APIの応答へ追加する`schedule_revision_candidates`（13.7）。

    遅れのある行を1件以上持つACTIVEな目標のうち、13.2の1日1回の判定で同じ報告対象日に
    既にAUTO生成済みの目標は除く。
    """
    goals = list(
        session.scalars(
            select(Goal).where(Goal.category == category, Goal.status == GoalStatus.ACTIVE)
        ).all()
    )
    if not goals:
        return []
    goal_ids = [goal.id for goal in goals]
    items = session.scalars(select(ScheduleItem).where(ScheduleItem.goal_id.in_(goal_ids))).all()
    delayed_goal_ids = {
        item.goal_id
        for item in items
        if schedule_service.compute_delay_kind(item, today) is not None
    }
    if not delayed_goal_ids:
        return []
    already_generated = set(
        session.scalars(
            select(ScheduleRevisionProposal.goal_id).where(
                ScheduleRevisionProposal.goal_id.in_(delayed_goal_ids),
                ScheduleRevisionProposal.trigger == ScheduleRevisionTrigger.AUTO,
                ScheduleRevisionProposal.record_date == target_date,
            )
        ).all()
    )
    return sorted(delayed_goal_ids - already_generated)


def get_pending_proposal(session: Session, goal_id: int) -> ScheduleRevisionProposal | None:
    """`GET /goals/{goal_id}/schedule`へ埋め込む未判断の修正案（13.7、目標ごとに最大1件）。"""
    return session.scalar(
        select(ScheduleRevisionProposal)
        .options(joinedload(ScheduleRevisionProposal.items))
        .where(
            ScheduleRevisionProposal.goal_id == goal_id,
            ScheduleRevisionProposal.status == ScheduleRevisionProposalStatus.PENDING,
        )
    )


def list_goal_ids_with_pending_proposal(session: Session, goal_ids: list[int]) -> set[int]:
    """ダッシュボードの案内（13.8）用。1クエリで一括取得する（N+1禁止）。"""
    if not goal_ids:
        return set()
    return set(
        session.scalars(
            select(ScheduleRevisionProposal.goal_id).where(
                ScheduleRevisionProposal.goal_id.in_(goal_ids),
                ScheduleRevisionProposal.status == ScheduleRevisionProposalStatus.PENDING,
            )
        ).all()
    )


def get_proposal_or_raise(session: Session, proposal_id: int) -> ScheduleRevisionProposal:
    proposal = session.scalar(
        select(ScheduleRevisionProposal)
        .options(joinedload(ScheduleRevisionProposal.items))
        .where(ScheduleRevisionProposal.id == proposal_id)
    )
    if proposal is None:
        raise NotFoundError("ScheduleRevisionProposal", proposal_id)
    return proposal


def _format_schedule_rows(
    items: list[ScheduleItem], today: dt.date, description_max_chars: int
) -> str:
    if not items:
        return _NO_SCHEDULE_ROWS_TEXT
    lines = []
    for item in items:
        delay_label = _DELAY_LABEL[schedule_service.compute_delay_kind(item, today)]
        description = (item.description or "").strip()[:description_max_chars] or "（なし）"
        actual_start = item.actual_start_date.isoformat() if item.actual_start_date else "なし"
        actual_end = item.actual_end_date.isoformat() if item.actual_end_date else "なし"
        lines.append(
            f"行ID: {item.id} / 作業項目: {item.title} / 作業内容: {description} / "
            f"予定開始日: {item.planned_start_date.isoformat()} / "
            f"予定終了日: {item.planned_end_date.isoformat()} / 状況: {item.status.value} / "
            f"実績開始日: {actual_start} / 実績終了日: {actual_end} / 遅れ: {delay_label}"
        )
    return "\n".join(lines)


def _format_recent_rejections(session: Session, goal: Goal, limit: int) -> str:
    """直近に却下した内容（D-64）。同じ目標の過去のすべての修正案を通じて、却下された
    変更行を却下日時の新しい順に`limit`件まで渡す。
    """
    rows = session.execute(
        select(ScheduleRevisionProposalItem, ScheduleItem.title)
        .join(
            ScheduleRevisionProposal,
            ScheduleRevisionProposalItem.proposal_id == ScheduleRevisionProposal.id,
        )
        .join(ScheduleItem, ScheduleRevisionProposalItem.schedule_item_id == ScheduleItem.id)
        .where(
            ScheduleRevisionProposal.goal_id == goal.id,
            ScheduleRevisionProposalItem.decision == ScheduleRevisionDecision.REJECTED,
        )
        .order_by(ScheduleRevisionProposalItem.decided_at.desc())
        .limit(limit)
    ).all()
    if not rows:
        return _NO_REJECTIONS_TEXT
    lines = []
    for proposal_item, title in rows:
        reason = proposal_item.reject_reason or "（理由の入力なし）"
        lines.append(
            f"作業項目: {title} / 却下された変更案: "
            f"予定開始日 {proposal_item.proposed_planned_start_date} → "
            f"予定終了日 {proposal_item.proposed_planned_end_date} / 却下理由: {reason}"
        )
    return "\n".join(lines)


def _build_daily_report_stages(
    session: Session, goal: Goal, today: dt.date
) -> list[prompt_builder.DegradableEntryStage]:
    """既存の日次報告文脈（週次要約＋直近の記録の2段階、13.3）を再利用する。

    `reading_feedback_service`等と同じ「period_end=today-1でtoday分の重複注入を避ける」方針
    （単位5開発Todo2章補足4。本用途では当日分はスケジュール行自体に反映済みのため、
    日次報告文脈側に当日入力を別途注入する必要が無い）。
    """
    period_end = today - dt.timedelta(days=1)
    if goal.category == GoalCategory.EXAM:
        period_start = goal.start_date
        raw_entries = ai_context_exam.build_recent_study_entries(
            session, goal, period_start, period_end
        )
    elif goal.category == GoalCategory.READING:
        book = goal.book
        period_start = book.start_date if book is not None else goal.start_date
        books = [book] if book is not None else []
        raw_entries = ai_context_reading.build_recent_recalls_entries(
            session, books, period_start, period_end
        )
    else:
        period_start = goal.start_date
        assignments = [goal.work_assignment] if goal.work_assignment is not None else []
        raw_entries = ai_context_work.build_recent_work_logs_entries(
            session, assignments, period_start, period_end
        )
    past_records = ai_context_common.build_past_record_entries(
        session, goal, period_start=period_start, period_end=period_end, raw_entries=raw_entries
    )
    return [
        prompt_builder.DegradableEntryStage(
            key="weekly_summaries",
            entries=past_records.weekly_summary_entries,
            empty_text=_NO_WEEKLY_SUMMARIES_TEXT,
        ),
        prompt_builder.DegradableEntryStage(
            key="recent_logs",
            entries=past_records.raw_entries,
            empty_text=_NO_RECENT_LOGS_TEXT,
        ),
    ]


def _call_ai(
    session: Session,
    goal: Goal,
    *,
    today: dt.date,
    deadline: dt.date | None,
    items: list[ScheduleItem],
) -> str:
    if not ai_client.is_authenticated(session):
        raise AiAuthRequiredError("AI connection is required")

    description_max_chars = setting_reader.get_int(
        session, SCHEDULE_REVISION_DESCRIPTION_MAX_CHARS_IN_PROMPT
    )
    rejections_limit = setting_reader.get_int(session, SCHEDULE_REVISION_RECENT_REJECTIONS_COUNT)
    stages = _build_daily_report_stages(session, goal, today)

    context = prompt_builder.DegradableFeedbackContext(
        fixed_variables={
            "today": today.isoformat(),
            "goal_category": goal.category.value,
            "goal_deadline": deadline.isoformat() if deadline is not None else _NO_DEADLINE_TEXT,
            "schedule_rows": _format_schedule_rows(items, today, description_max_chars),
            "recent_rejections": _format_recent_rejections(session, goal, rejections_limit),
        },
        stages=stages,
    )
    template_body = ai_orchestration.load_template_body(session, AiPurpose.SCHEDULE_REVISION)
    max_chars = ai_orchestration.get_max_prompt_chars(session)
    if prompt_builder.exceeds_with_entries_emptied(template_body, context, max_chars):
        raise ScheduleRevisionPromptTooLongError(f"prompt exceeds the limit: goal_id={goal.id}")
    build_result = prompt_builder.build_with_degradable_entries(template_body, context, max_chars)

    folder_name = setting_reader.get_str(session, AI_SCHEDULE_REVISION_FOLDER_NAME)
    conversation = ai_conversation.ensure_conversation(
        session,
        goal=goal,
        scope=ConversationScope.SCHEDULE_REVISION,
        scope_key=uuid.uuid4().hex,
        assistant_uid=setting_reader.get_str(session, AI_ASSISTANT_UID_SCHEDULE_REVISION),
        title=f"{goal.name} スケジュール修正案",
        folder_name=folder_name,
    )
    try:
        result = ai_orchestration.send_and_log(
            session,
            purpose=AiPurpose.SCHEDULE_REVISION,
            conversation=conversation,
            prompt_text=build_result.text,
            prompt_chars=build_result.prompt_chars,
            was_truncated=build_result.was_truncated,
        )
    finally:
        ai_conversation.discard_conversation(session, conversation, folder_name=folder_name)
    return result.response_text


def _parse_date(raw: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


@dataclass(frozen=True)
class _ValidatedChange:
    item: ScheduleItem
    planned_start_date: dt.date
    planned_end_date: dt.date
    reason: str


@dataclass(frozen=True)
class _ValidatedWarning:
    item: ScheduleItem
    reason: str


def _validate_changes(
    blocks: list[schedule_revision_block_parsing.ParsedChangeBlock],
    items_by_id: dict[int, ScheduleItem],
    *,
    today: dt.date,
    deadline: dt.date | None,
    reason_max_chars: int,
) -> list[_ValidatedChange]:
    """13.5の検証（CHANGEブロック）。不正・制約違反のブロックは個別に捨てる（D-61）。"""
    validated: list[_ValidatedChange] = []
    seen_ids: set[int] = set()
    for block in blocks:
        try:
            item_id = int(block.item_id_raw)
        except ValueError:  # pragma: no cover - 行IDは`[0-9]+`の正規表現で既に数字限定
            continue
        if item_id in seen_ids:
            continue  # 重複は最初のものだけを使う（13.5）。
        item = items_by_id.get(item_id)
        if item is None:
            continue  # 行ID: 対象の目標に属する行であること（他目標・不存在IDを拒否）。
        if item.status not in (ScheduleItemStatus.NOT_STARTED, ScheduleItemStatus.IN_PROGRESS):
            continue  # 状況: 未着手または進行中の行だけ。
        new_start = _parse_date(block.planned_start_date_raw)
        new_end = _parse_date(block.planned_end_date_raw)
        if new_start is None or new_end is None:
            continue
        if item.status == ScheduleItemStatus.IN_PROGRESS and new_start != item.planned_start_date:
            continue  # 進行中の行: 予定開始日は現在の値と同じであること（変更不可）。
        if new_start > new_end:
            continue
        if new_end < today:
            continue  # 新しい予定日: 本日以降。
        if item.status == ScheduleItemStatus.NOT_STARTED and new_start < today:
            continue
        if deadline is not None and new_end > deadline:
            continue  # 期限: 目標に期限がある場合、新しい予定終了日 ≦ 期限。
        reason = block.reason.strip()
        if not reason or len(reason) > reason_max_chars:
            continue  # 理由: 必須。上限文字数以内。
        if new_start == item.planned_start_date and new_end == item.planned_end_date:
            continue  # 差分: 現在の値と少なくとも1つ異なること。
        seen_ids.add(item_id)
        validated.append(
            _ValidatedChange(
                item=item, planned_start_date=new_start, planned_end_date=new_end, reason=reason
            )
        )
    return validated


def _validate_warnings(
    blocks: list[schedule_revision_block_parsing.ParsedWarningBlock],
    items_by_id: dict[int, ScheduleItem],
    *,
    reason_max_chars: int,
) -> list[_ValidatedWarning]:
    """13.5の検証（WARNINGブロック）。注意ブロックは行IDの所属と理由の必須のみを課す
    （13.5「注意ブロック」行、CHANGE向けの状況・日付・期限の制約は適用しない）。
    """
    validated: list[_ValidatedWarning] = []
    seen_ids: set[int] = set()
    for block in blocks:
        try:
            item_id = int(block.item_id_raw)
        except ValueError:  # pragma: no cover - 行IDは`[0-9]+`の正規表現で既に数字限定
            continue
        if item_id in seen_ids:  # 重複は最初のものだけを使う（13.5）。
            continue
        item = items_by_id.get(item_id)
        if item is None:  # 行ID: 対象の目標に属する行であること。
            continue
        reason = block.reason.strip()
        if not reason or len(reason) > reason_max_chars:  # 理由: 必須。上限文字数以内。
            continue
        seen_ids.add(item_id)
        validated.append(_ValidatedWarning(item=item, reason=reason))
    return validated


def _supersede_pending_proposal(session: Session, goal_id: int) -> None:
    """D-65：新しい修正案ができた場合、古い修正案の未判断の行を置き換え済みとして終了する。"""
    pending = session.scalar(
        select(ScheduleRevisionProposal)
        .options(joinedload(ScheduleRevisionProposal.items))
        .where(
            ScheduleRevisionProposal.goal_id == goal_id,
            ScheduleRevisionProposal.status == ScheduleRevisionProposalStatus.PENDING,
        )
    )
    if pending is None:
        return
    pending.status = ScheduleRevisionProposalStatus.SUPERSEDED
    for item in pending.items:
        if item.decision == ScheduleRevisionDecision.PENDING:
            item.decision = ScheduleRevisionDecision.SUPERSEDED
    session.flush()


def generate_proposal(
    session: Session,
    goal: Goal,
    *,
    trigger: ScheduleRevisionTrigger,
    record_date: dt.date | None,
    today: dt.date,
) -> ScheduleRevisionProposal | None:
    """修正案を生成する（13.1〜13.6）。

    AUTOで遅れのある行が1件も無い場合はAIを呼ばず`None`を返す（「対象なし」、D-54）。
    MANUALは遅れが無くても常にAIを呼ぶ（D-58）。有効な変更・注意のいずれも無い場合も
    `None`を返す（「修正が必要な行はありませんでした」、13.5）。
    """
    goal_service.ensure_goal_editable(goal)

    items = _goal_items(session, goal.id)
    items_by_id = {item.id: item for item in items}

    if trigger == ScheduleRevisionTrigger.AUTO:
        has_delay = any(
            schedule_service.compute_delay_kind(item, today) is not None for item in items
        )
        if not has_delay:
            return None

    deadline = resolve_goal_due_date(goal)
    response_text = _call_ai(session, goal, today=today, deadline=deadline, items=items)

    max_block_chars = setting_reader.get_int(session, SCHEDULE_REVISION_MAX_BLOCK_CHARS)
    reason_max_chars = setting_reader.get_int(session, SCHEDULE_REVISION_REASON_MAX_CHARS)
    parsed = schedule_revision_block_parsing.parse_response(
        response_text, max_block_chars=max_block_chars
    )

    validated_changes = _validate_changes(
        parsed.changes,
        items_by_id,
        today=today,
        deadline=deadline,
        reason_max_chars=reason_max_chars,
    )
    validated_warnings = _validate_warnings(
        parsed.warnings, items_by_id, reason_max_chars=reason_max_chars
    )
    if not validated_changes and not validated_warnings:
        return None

    summary = parsed.summary.strip()[:reason_max_chars] if parsed.summary else None

    with serialize_writes():
        _supersede_pending_proposal(session, goal.id)
        proposal = ScheduleRevisionProposal(
            goal_id=goal.id,
            trigger=trigger,
            record_date=record_date,
            summary=summary,
            status=ScheduleRevisionProposalStatus.PENDING,
        )
        session.add(proposal)
        session.flush()
        for change in validated_changes:
            session.add(
                ScheduleRevisionProposalItem(
                    proposal_id=proposal.id,
                    schedule_item_id=change.item.id,
                    kind=ScheduleRevisionItemKind.CHANGE,
                    before_planned_start_date=change.item.planned_start_date,
                    before_planned_end_date=change.item.planned_end_date,
                    before_status=change.item.status,
                    proposed_planned_start_date=change.planned_start_date,
                    proposed_planned_end_date=change.planned_end_date,
                    reason=change.reason,
                    decision=ScheduleRevisionDecision.PENDING,
                )
            )
        for warning in validated_warnings:
            session.add(
                ScheduleRevisionProposalItem(
                    proposal_id=proposal.id,
                    schedule_item_id=warning.item.id,
                    kind=ScheduleRevisionItemKind.WARNING,
                    before_planned_start_date=warning.item.planned_start_date,
                    before_planned_end_date=warning.item.planned_end_date,
                    before_status=warning.item.status,
                    proposed_planned_start_date=None,
                    proposed_planned_end_date=None,
                    reason=warning.reason,
                    decision=ScheduleRevisionDecision.PENDING,
                )
            )
        session.commit()
    return proposal


@dataclass(frozen=True)
class DecisionOutcome:
    proposal_item_id: int
    applied: bool
    blocked_reason: str | None


def decide(
    session: Session,
    goal: Goal,
    proposal: ScheduleRevisionProposal,
    decisions: list[ScheduleRevisionDecisionInput],
    today: dt.date,
) -> list[DecisionOutcome]:
    """判断API（13.7）。検証を適用より先にすべて終え（単位2`save_schedule`と同じ方針）、
    「変更前の値が現在の値と一致しない」行（D-59）だけは適用の段階で検知し、その行だけを
    結果へ返して他の行の処理は継続する。
    """
    goal_service.ensure_goal_editable(goal)
    if proposal.goal_id != goal.id:
        raise NotFoundError("ScheduleRevisionProposal", proposal.id)
    if proposal.status != ScheduleRevisionProposalStatus.PENDING:
        raise ScheduleRevisionProposalNotPendingError(proposal.id)

    items_by_id = {item.id: item for item in proposal.items}
    resolved: list[tuple[ScheduleRevisionProposalItem, ScheduleItem, dict]] = []

    # --- 検証（適用より先にすべて終える） ---
    for decision_input in decisions:
        proposal_item = items_by_id.get(decision_input.proposal_item_id)
        if proposal_item is None:
            raise ValidationError(
                f"Cannot decide proposal item(id={decision_input.proposal_item_id}) "
                "that belongs to a different proposal"
            )
        if proposal_item.decision != ScheduleRevisionDecision.PENDING:
            raise ValidationError(
                f"ScheduleRevisionProposalItem(id={proposal_item.id}) is already decided"
            )
        schedule_item = session.get(ScheduleItem, proposal_item.schedule_item_id)
        if schedule_item is None:  # pragma: no cover - ON DELETE CASCADEで通常到達しない
            # schedule_itemはON DELETE CASCADEでproposal_item自体も削除されるため、通常は
            # 到達しない防御的分岐（異常系、CODING_RULES.md）。
            raise ValidationError(
                f"ScheduleItem(id={proposal_item.schedule_item_id}) no longer exists"
            )

        if decision_input.decision == ScheduleRevisionDecision.ACKNOWLEDGED:
            if proposal_item.kind != ScheduleRevisionItemKind.WARNING:
                raise ValidationError("ACKNOWLEDGED is only valid for WARNING rows")
            resolved.append((proposal_item, schedule_item, {"decision": "ACKNOWLEDGED"}))
            continue

        if proposal_item.kind != ScheduleRevisionItemKind.CHANGE:
            raise ValidationError("APPROVED/REJECTED is only valid for CHANGE rows")

        if decision_input.decision == ScheduleRevisionDecision.REJECTED:
            resolved.append(
                (
                    proposal_item,
                    schedule_item,
                    {"decision": "REJECTED", "reject_reason": decision_input.reject_reason},
                )
            )
            continue

        if decision_input.decision != ScheduleRevisionDecision.APPROVED:
            raise ValidationError(f"Unsupported decision: {decision_input.decision}")

        new_start = decision_input.planned_start_date or proposal_item.proposed_planned_start_date
        new_end = decision_input.planned_end_date or proposal_item.proposed_planned_end_date
        # 第6章の検証ルール＋13.5「新しい予定日」「進行中の行」を適用する。期限（D-62）は
        # 利用者の判断を優先して適用しない（13.7）。
        if (
            schedule_item.status == ScheduleItemStatus.IN_PROGRESS
            and new_start != schedule_item.planned_start_date
        ):
            raise ValidationError("IN_PROGRESS items cannot change planned_start_date")
        if new_start > new_end:
            raise ValidationError("planned_start_date must not be after planned_end_date")
        if new_end < today or (
            schedule_item.status == ScheduleItemStatus.NOT_STARTED and new_start < today
        ):
            raise ValidationError("planned dates must not be before today")
        resolved.append(
            (
                proposal_item,
                schedule_item,
                {
                    "decision": "APPROVED",
                    "planned_start_date": new_start,
                    "planned_end_date": new_end,
                },
            )
        )

    # --- 適用（stale行はここで判定し、他の行の処理には影響させない、D-59） ---
    outcomes: list[DecisionOutcome] = []
    now = utcnow()
    bumped = False
    for proposal_item, schedule_item, action in resolved:
        if action["decision"] == "APPROVED":
            is_stale = (
                proposal_item.before_planned_start_date != schedule_item.planned_start_date
                or proposal_item.before_planned_end_date != schedule_item.planned_end_date
                or proposal_item.before_status != schedule_item.status
            )
            if is_stale:
                outcomes.append(DecisionOutcome(proposal_item.id, False, "STALE_BEFORE_VALUE"))
                continue
            schedule_item.planned_start_date = action["planned_start_date"]
            schedule_item.planned_end_date = action["planned_end_date"]
            proposal_item.decision = ScheduleRevisionDecision.APPROVED
            proposal_item.applied_planned_start_date = action["planned_start_date"]
            proposal_item.applied_planned_end_date = action["planned_end_date"]
            proposal_item.decided_at = now
            bumped = True
        elif action["decision"] == "REJECTED":
            proposal_item.decision = ScheduleRevisionDecision.REJECTED
            proposal_item.reject_reason = action["reject_reason"]
            proposal_item.decided_at = now
        else:
            proposal_item.decision = ScheduleRevisionDecision.ACKNOWLEDGED
            proposal_item.decided_at = now
        outcomes.append(DecisionOutcome(proposal_item.id, True, None))

    session.flush()
    if bumped:
        schedule_service.bump_schedule_revision(session, goal.id)
    if all(item.decision != ScheduleRevisionDecision.PENDING for item in proposal.items):
        proposal.status = ScheduleRevisionProposalStatus.RESOLVED
    session.flush()
    return outcomes
