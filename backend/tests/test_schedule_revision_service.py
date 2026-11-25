"""schedule_revision_service の単体テスト（開発Todo_スケジュール・ガントチャート_v1.1
第13章・13.10、単位5）。実際のAI基盤へは接続せず、`tests.ai_chat_fakes.FakeAi`で
`app.ai.client`の通信関数を差し替える（ヘルプ・目標相談・まとめと同じ方針）。
"""

import datetime as dt
import sqlite3

import pytest
from sqlalchemy import select

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.ai.exceptions import AiAuthRequiredError
from app.constants.enums import (
    GoalStatus,
    ScheduleItemStatus,
    ScheduleRevisionDecision,
    ScheduleRevisionItemKind,
    ScheduleRevisionProposalStatus,
    ScheduleRevisionTrigger,
)
from app.database import engine
from app.models.ai import AiConversation
from app.models.schedule import GoalSchedule
from app.models.schedule_revision import ScheduleRevisionProposal, ScheduleRevisionProposalItem
from app.schemas.schedule_revision import ScheduleRevisionDecisionInput
from app.services import schedule_revision_service as service
from app.services.exceptions import (
    NotFoundError,
    ScheduleRevisionPromptTooLongError,
    ScheduleRevisionProposalNotPendingError,
    ValidationError,
)
from tests.ai_chat_fakes import FakeAi
from tests.schedule_revision_helpers import (
    TODAY,
    add_fixed_exam_subject,
    add_range_exam_subject,
    make_exam_goal,
    make_item,
    make_reading_goal,
    make_work_goal,
)


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _change_block(item_id: int, start: str, end: str, reason: str = "遅れています") -> str:
    return f"種類: 変更\n行ID: {item_id}\n予定開始日: {start}\n予定終了日: {end}\n理由: {reason}"


def _warning_block(item_id: int, reason: str = "期限内に収まりません") -> str:
    return f"種類: 注意\n行ID: {item_id}\n理由: {reason}"


class TestResolveGoalDueDate:
    def test_exam_with_fixed_subject_returns_the_day_before(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        add_fixed_exam_subject(seeded_session, goal, exam_date_fixed=dt.date(2026, 12, 1))

        assert service.resolve_goal_due_date(goal) == dt.date(2026, 11, 30)

    def test_exam_with_range_subject_uses_the_start_of_the_range(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        add_range_exam_subject(
            seeded_session,
            goal,
            exam_date_from=dt.date(2026, 12, 10),
            exam_date_to=dt.date(2026, 12, 12),
        )

        assert service.resolve_goal_due_date(goal) == dt.date(2026, 12, 9)

    def test_exam_with_multiple_subjects_uses_the_earliest(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        add_fixed_exam_subject(seeded_session, goal, exam_date_fixed=dt.date(2026, 12, 20))
        add_range_exam_subject(
            seeded_session,
            goal,
            exam_date_from=dt.date(2026, 12, 1),
            exam_date_to=dt.date(2026, 12, 3),
        )

        assert service.resolve_goal_due_date(goal) == dt.date(2026, 11, 30)

    def test_exam_without_subjects_returns_none(self, seeded_session):
        goal = make_exam_goal(seeded_session)

        assert service.resolve_goal_due_date(goal) is None

    def test_reading_returns_book_due_date(self, seeded_session):
        goal = make_reading_goal(seeded_session, due_date=dt.date(2026, 6, 30))

        assert service.resolve_goal_due_date(goal) == dt.date(2026, 6, 30)

    def test_work_has_no_deadline(self, seeded_session):
        goal = make_work_goal(seeded_session)

        assert service.resolve_goal_due_date(goal) is None


class TestListRevisionCandidateGoalIds:
    def test_includes_a_goal_with_an_end_delayed_item(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )

        candidates = service.list_revision_candidate_goal_ids(
            seeded_session, goal.category, TODAY, TODAY
        )

        assert candidates == [goal.id]

    def test_excludes_a_goal_with_no_delayed_item(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 26),
            planned_end_date=dt.date(2026, 12, 20),
        )

        candidates = service.list_revision_candidate_goal_ids(
            seeded_session, goal.category, TODAY, TODAY
        )

        assert candidates == []

    def test_excludes_a_goal_already_auto_generated_for_the_same_record_date(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        seeded_session.add(
            ScheduleRevisionProposal(
                goal_id=goal.id,
                trigger=ScheduleRevisionTrigger.AUTO,
                record_date=TODAY,
                status=ScheduleRevisionProposalStatus.RESOLVED,
            )
        )
        seeded_session.flush()

        candidates = service.list_revision_candidate_goal_ids(
            seeded_session, goal.category, TODAY, TODAY
        )

        assert candidates == []

    def test_a_manual_proposal_for_the_same_date_does_not_exclude_the_goal(self, seeded_session):
        """AUTO専用の判定のため、MANUALで生成済みでも除外しない（13.2は自動生成の重複防止）。"""
        goal = make_exam_goal(seeded_session)
        make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        seeded_session.add(
            ScheduleRevisionProposal(
                goal_id=goal.id,
                trigger=ScheduleRevisionTrigger.MANUAL,
                record_date=None,
                status=ScheduleRevisionProposalStatus.RESOLVED,
            )
        )
        seeded_session.flush()

        candidates = service.list_revision_candidate_goal_ids(
            seeded_session, goal.category, TODAY, TODAY
        )

        assert candidates == [goal.id]

    def test_excludes_a_non_active_goal(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        goal.status = GoalStatus.PAUSED
        seeded_session.flush()

        candidates = service.list_revision_candidate_goal_ids(
            seeded_session, goal.category, TODAY, TODAY
        )

        assert candidates == []


class TestGenerateProposal:
    def test_auto_trigger_without_any_delay_returns_none_and_does_not_call_ai(
        self, seeded_session, monkeypatch
    ):
        goal = make_exam_goal(seeded_session)
        make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 26),
            planned_end_date=dt.date(2026, 12, 20),
        )
        fake = FakeAi(monkeypatch, ("総評: 対象なし",))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None
        assert fake.sent == []

    def test_manual_trigger_without_any_delay_still_calls_ai(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 26),
            planned_end_date=dt.date(2026, 12, 20),
        )
        fake = FakeAi(monkeypatch, (_change_block(item.id, "2026-11-26", "2026-12-25"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.MANUAL,
            record_date=None,
            today=TODAY,
        )

        assert len(fake.sent) == 1
        assert proposal is not None
        assert len(proposal.items) == 1

    def test_valid_change_block_creates_a_pending_proposal_item(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (_change_block(item.id, "2026-11-26", "2026-12-05"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is not None
        assert proposal.status == ScheduleRevisionProposalStatus.PENDING
        assert len(proposal.items) == 1
        proposal_item = proposal.items[0]
        assert proposal_item.kind == ScheduleRevisionItemKind.CHANGE
        assert proposal_item.schedule_item_id == item.id
        assert proposal_item.proposed_planned_start_date == dt.date(2026, 11, 26)
        assert proposal_item.proposed_planned_end_date == dt.date(2026, 12, 5)
        assert proposal_item.before_planned_start_date == item.planned_start_date
        assert proposal_item.decision == ScheduleRevisionDecision.PENDING

    def test_discards_a_change_block_for_another_goals_row(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session, name="目標A")
        other_goal = make_exam_goal(seeded_session, name="目標B")
        make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        other_item = make_item(
            seeded_session,
            other_goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (_change_block(other_item.id, "2026-11-26", "2026-12-05"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None

    def test_discards_a_change_for_a_done_item(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        delayed = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        done_item = make_item(
            seeded_session,
            goal,
            title="完了済み",
            planned_start_date=dt.date(2026, 10, 1),
            planned_end_date=dt.date(2026, 10, 10),
            status=ScheduleItemStatus.DONE,
            actual_start_date=dt.date(2026, 10, 1),
            actual_end_date=dt.date(2026, 10, 10),
            display_order=1,
        )
        FakeAi(monkeypatch, (_change_block(done_item.id, "2026-11-26", "2026-12-05"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None
        assert delayed.id  # 遅れている行自体は存在する（対象判定には使われただけ）

    def test_discards_a_change_that_moves_the_start_date_of_an_in_progress_item(
        self, seeded_session, monkeypatch
    ):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
            status=ScheduleItemStatus.IN_PROGRESS,
            actual_start_date=dt.date(2026, 11, 1),
        )
        FakeAi(monkeypatch, (_change_block(item.id, "2026-11-05", "2026-12-05"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None

    def test_accepts_an_end_date_only_change_for_an_in_progress_item(
        self, seeded_session, monkeypatch
    ):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
            status=ScheduleItemStatus.IN_PROGRESS,
            actual_start_date=dt.date(2026, 11, 1),
        )
        FakeAi(monkeypatch, (_change_block(item.id, "2026-11-01", "2026-12-05"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is not None
        assert proposal.items[0].proposed_planned_start_date == dt.date(2026, 11, 1)
        assert proposal.items[0].proposed_planned_end_date == dt.date(2026, 12, 5)

    def test_discards_a_change_beyond_the_goal_deadline(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        add_fixed_exam_subject(seeded_session, goal, exam_date_fixed=dt.date(2026, 12, 1))
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (_change_block(item.id, "2026-11-26", "2026-12-10"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None

    def test_discards_a_change_with_a_past_date(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (_change_block(item.id, "2026-11-10", "2026-11-15"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None

    def test_discards_a_not_started_change_whose_new_start_is_before_today(
        self, seeded_session, monkeypatch
    ):
        """未着手の行で新しい予定終了日は本日以降だが、新しい予定開始日が本日より前の場合。"""
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (_change_block(item.id, "2026-11-20", "2026-11-30"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None

    def test_discards_a_change_with_a_blank_reason(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        blank_reason_block = (
            f"種類: 変更\n行ID: {item.id}\n予定開始日: 2026-11-26\n予定終了日: 2026-12-01\n理由: "
        )
        FakeAi(monkeypatch, (blank_reason_block,))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None

    def test_discards_a_change_identical_to_the_current_value(self, seeded_session, monkeypatch):
        # new_start>=today（開始の遅れチェックに先に拾われないよう未来日にする）で、
        # 差分チェック自体（397行目）に到達させる。
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 26),
            planned_end_date=dt.date(2026, 12, 1),
        )
        FakeAi(monkeypatch, (_change_block(item.id, "2026-11-26", "2026-12-01"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None

    def test_duplicate_item_id_blocks_use_only_the_first(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        response = "\n===\n".join(
            [
                _change_block(item.id, "2026-11-26", "2026-12-01", reason="最初"),
                _change_block(item.id, "2026-11-27", "2026-12-02", reason="2番目"),
            ]
        )
        FakeAi(monkeypatch, (response,))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert len(proposal.items) == 1
        assert proposal.items[0].reason == "最初"

    def test_valid_warning_block_creates_a_warning_item(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (_warning_block(item.id),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is not None
        assert proposal.items[0].kind == ScheduleRevisionItemKind.WARNING
        assert proposal.items[0].proposed_planned_start_date is None

    def test_no_valid_blocks_returns_none(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, ("総評: 特に提案はありません",))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None

    def test_a_new_proposal_supersedes_the_old_pending_one(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (_change_block(item.id, "2026-11-26", "2026-12-01"),))
        first = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )
        first_id = first.id
        first_item_id = first.items[0].id

        FakeAi(monkeypatch, (_change_block(item.id, "2026-11-27", "2026-12-02"),))
        second = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.MANUAL,
            record_date=None,
            today=TODAY,
        )

        seeded_session.flush()
        refreshed_first = seeded_session.get(ScheduleRevisionProposal, first_id)
        refreshed_first_item = seeded_session.get(ScheduleRevisionProposalItem, first_item_id)
        assert refreshed_first.status == ScheduleRevisionProposalStatus.SUPERSEDED
        assert refreshed_first_item.decision == ScheduleRevisionDecision.SUPERSEDED
        assert second.status == ScheduleRevisionProposalStatus.PENDING

    def test_discards_a_malformed_date_block(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        malformed = (
            f"種類: 変更\n行ID: {item.id}\n予定開始日: 来週\n予定終了日: 2026-12-01\n"
            "理由: 不正な日付"
        )
        FakeAi(monkeypatch, (malformed,))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None

    def test_does_not_hold_the_write_lock_during_the_ai_call(self, seeded_session, monkeypatch):
        """CODING_RULES.md「AI通信とトランザクション」: AI応答の待機中は書き込みロックを
        保持しない（test_ai_write_lock.pyと同じ観点、ユーザー指示の重点確認）。
        """
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        seeded_session.commit()

        def _write_lock_is_free() -> bool:
            connection = sqlite3.connect(engine.url.database, timeout=0.2)
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.rollback()
                return True
            except sqlite3.OperationalError:
                return False
            finally:
                connection.close()

        lock_free_at_call = []
        fake = FakeAi(monkeypatch, (_change_block(item.id, "2026-11-26", "2026-12-01"),))
        original_send = fake._send

        def _probing_send(session, *, chat_uid, message):
            lock_free_at_call.append(_write_lock_is_free())
            return original_send(session, chat_uid=chat_uid, message=message)

        monkeypatch.setattr(ai_client, "send_message", _probing_send)

        service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert lock_free_at_call == [True]

    def test_conversation_is_discarded_after_sending(self, seeded_session, monkeypatch):
        """13.3「1回ごとに完結する呼び出しとし、会話は継続しない」：送信後は会話行が残らない。"""
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (_change_block(item.id, "2026-11-26", "2026-12-01"),))

        service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert seeded_session.query(AiConversation).count() == 0


class TestDecide:
    def _make_pending_change_proposal(self, session, goal, item, *, proposed_start, proposed_end):
        proposal = ScheduleRevisionProposal(
            goal_id=goal.id,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            status=ScheduleRevisionProposalStatus.PENDING,
        )
        session.add(proposal)
        session.flush()
        proposal_item = ScheduleRevisionProposalItem(
            proposal_id=proposal.id,
            schedule_item_id=item.id,
            kind=ScheduleRevisionItemKind.CHANGE,
            before_planned_start_date=item.planned_start_date,
            before_planned_end_date=item.planned_end_date,
            before_status=item.status,
            proposed_planned_start_date=proposed_start,
            proposed_planned_end_date=proposed_end,
            reason="遅れています",
            decision=ScheduleRevisionDecision.PENDING,
        )
        session.add(proposal_item)
        session.flush()
        session.refresh(proposal)
        return proposal, proposal_item

    def test_approving_applies_the_proposed_dates_and_bumps_the_revision(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal, proposal_item = self._make_pending_change_proposal(
            seeded_session,
            goal,
            item,
            proposed_start=dt.date(2026, 11, 26),
            proposed_end=dt.date(2026, 12, 1),
        )

        outcomes = service.decide(
            seeded_session,
            goal,
            proposal,
            [
                ScheduleRevisionDecisionInput(
                    proposal_item_id=proposal_item.id, decision=ScheduleRevisionDecision.APPROVED
                )
            ],
            TODAY,
        )

        assert outcomes[0].applied is True
        assert item.planned_start_date == dt.date(2026, 11, 26)
        assert item.planned_end_date == dt.date(2026, 12, 1)
        assert proposal_item.decision == ScheduleRevisionDecision.APPROVED
        assert proposal.status == ScheduleRevisionProposalStatus.RESOLVED
        schedule = seeded_session.scalar(
            select(GoalSchedule).where(GoalSchedule.goal_id == goal.id)
        )
        assert schedule.revision == 1

    def test_approving_with_a_user_override_ignores_the_deadline(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        add_fixed_exam_subject(seeded_session, goal, exam_date_fixed=dt.date(2026, 12, 1))
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal, proposal_item = self._make_pending_change_proposal(
            seeded_session,
            goal,
            item,
            proposed_start=dt.date(2026, 11, 26),
            proposed_end=dt.date(2026, 11, 28),
        )

        outcomes = service.decide(
            seeded_session,
            goal,
            proposal,
            [
                ScheduleRevisionDecisionInput(
                    proposal_item_id=proposal_item.id,
                    decision=ScheduleRevisionDecision.APPROVED,
                    planned_end_date=dt.date(2026, 12, 15),
                )
            ],
            TODAY,
        )

        assert outcomes[0].applied is True
        assert item.planned_end_date == dt.date(2026, 12, 15)

    def test_rejecting_sets_the_reason_without_changing_the_schedule(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        original_end = item.planned_end_date
        proposal, proposal_item = self._make_pending_change_proposal(
            seeded_session,
            goal,
            item,
            proposed_start=dt.date(2026, 11, 26),
            proposed_end=dt.date(2026, 12, 1),
        )

        service.decide(
            seeded_session,
            goal,
            proposal,
            [
                ScheduleRevisionDecisionInput(
                    proposal_item_id=proposal_item.id,
                    decision=ScheduleRevisionDecision.REJECTED,
                    reject_reason="まだ早い",
                )
            ],
            TODAY,
        )

        assert item.planned_end_date == original_end
        assert proposal_item.decision == ScheduleRevisionDecision.REJECTED
        assert proposal_item.reject_reason == "まだ早い"

    def test_acknowledging_a_warning_row(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal = ScheduleRevisionProposal(
            goal_id=goal.id,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            status=ScheduleRevisionProposalStatus.PENDING,
        )
        seeded_session.add(proposal)
        seeded_session.flush()
        proposal_item = ScheduleRevisionProposalItem(
            proposal_id=proposal.id,
            schedule_item_id=item.id,
            kind=ScheduleRevisionItemKind.WARNING,
            before_planned_start_date=item.planned_start_date,
            before_planned_end_date=item.planned_end_date,
            before_status=item.status,
            reason="期限内に収まりません",
            decision=ScheduleRevisionDecision.PENDING,
        )
        seeded_session.add(proposal_item)
        seeded_session.flush()
        seeded_session.refresh(proposal)

        service.decide(
            seeded_session,
            goal,
            proposal,
            [
                ScheduleRevisionDecisionInput(
                    proposal_item_id=proposal_item.id,
                    decision=ScheduleRevisionDecision.ACKNOWLEDGED,
                )
            ],
            TODAY,
        )

        assert proposal_item.decision == ScheduleRevisionDecision.ACKNOWLEDGED

    def test_approving_a_stale_row_is_skipped_without_blocking_other_rows(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        item_a = make_item(
            seeded_session,
            goal,
            title="行A",
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        item_b = make_item(
            seeded_session,
            goal,
            title="行B",
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
            display_order=1,
        )
        proposal = ScheduleRevisionProposal(
            goal_id=goal.id,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            status=ScheduleRevisionProposalStatus.PENDING,
        )
        seeded_session.add(proposal)
        seeded_session.flush()
        item_a_row = ScheduleRevisionProposalItem(
            proposal_id=proposal.id,
            schedule_item_id=item_a.id,
            kind=ScheduleRevisionItemKind.CHANGE,
            before_planned_start_date=item_a.planned_start_date,
            before_planned_end_date=item_a.planned_end_date,
            before_status=item_a.status,
            proposed_planned_start_date=dt.date(2026, 11, 26),
            proposed_planned_end_date=dt.date(2026, 12, 1),
            reason="遅れています",
            decision=ScheduleRevisionDecision.PENDING,
        )
        item_b_row = ScheduleRevisionProposalItem(
            proposal_id=proposal.id,
            schedule_item_id=item_b.id,
            kind=ScheduleRevisionItemKind.CHANGE,
            before_planned_start_date=item_b.planned_start_date,
            before_planned_end_date=item_b.planned_end_date,
            before_status=item_b.status,
            proposed_planned_start_date=dt.date(2026, 11, 27),
            proposed_planned_end_date=dt.date(2026, 12, 2),
            reason="遅れています",
            decision=ScheduleRevisionDecision.PENDING,
        )
        seeded_session.add_all([item_a_row, item_b_row])
        seeded_session.flush()
        seeded_session.refresh(proposal)
        # 行Aはスケジュール画面で既に編集済み（before値と現在値が一致しない状態）。
        item_a.planned_end_date = dt.date(2026, 11, 22)
        seeded_session.flush()

        outcomes = service.decide(
            seeded_session,
            goal,
            proposal,
            [
                ScheduleRevisionDecisionInput(
                    proposal_item_id=item_a_row.id, decision=ScheduleRevisionDecision.APPROVED
                ),
                ScheduleRevisionDecisionInput(
                    proposal_item_id=item_b_row.id, decision=ScheduleRevisionDecision.APPROVED
                ),
            ],
            TODAY,
        )

        outcomes_by_id = {o.proposal_item_id: o for o in outcomes}
        assert outcomes_by_id[item_a_row.id].applied is False
        assert outcomes_by_id[item_a_row.id].blocked_reason == "STALE_BEFORE_VALUE"
        assert outcomes_by_id[item_b_row.id].applied is True
        assert item_b.planned_start_date == dt.date(2026, 11, 27)
        assert item_a_row.decision == ScheduleRevisionDecision.PENDING
        assert item_b_row.decision == ScheduleRevisionDecision.APPROVED
        # 行Aが未判断のまま残るため、修正案全体はまだRESOLVEDにならない。
        assert proposal.status == ScheduleRevisionProposalStatus.PENDING

    def test_raises_when_the_proposal_is_not_pending(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal, proposal_item = self._make_pending_change_proposal(
            seeded_session,
            goal,
            item,
            proposed_start=dt.date(2026, 11, 26),
            proposed_end=dt.date(2026, 12, 1),
        )
        proposal.status = ScheduleRevisionProposalStatus.RESOLVED
        seeded_session.flush()

        with pytest.raises(ScheduleRevisionProposalNotPendingError):
            service.decide(
                seeded_session,
                goal,
                proposal,
                [
                    ScheduleRevisionDecisionInput(
                        proposal_item_id=proposal_item.id,
                        decision=ScheduleRevisionDecision.APPROVED,
                    )
                ],
                TODAY,
            )

    def test_raises_not_found_when_the_proposal_belongs_to_a_different_goal(self, seeded_session):
        goal = make_exam_goal(seeded_session, name="目標A")
        other_goal = make_exam_goal(seeded_session, name="目標B")
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal, proposal_item = self._make_pending_change_proposal(
            seeded_session,
            goal,
            item,
            proposed_start=dt.date(2026, 11, 26),
            proposed_end=dt.date(2026, 12, 1),
        )

        with pytest.raises(NotFoundError):
            service.decide(
                seeded_session,
                other_goal,
                proposal,
                [
                    ScheduleRevisionDecisionInput(
                        proposal_item_id=proposal_item.id,
                        decision=ScheduleRevisionDecision.APPROVED,
                    )
                ],
                TODAY,
            )

    def test_raises_when_moving_the_start_date_of_an_in_progress_item_via_override(
        self, seeded_session
    ):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
            status=ScheduleItemStatus.IN_PROGRESS,
            actual_start_date=dt.date(2026, 11, 1),
        )
        proposal, proposal_item = self._make_pending_change_proposal(
            seeded_session,
            goal,
            item,
            proposed_start=dt.date(2026, 11, 1),
            proposed_end=dt.date(2026, 12, 1),
        )

        with pytest.raises(ValidationError):
            service.decide(
                seeded_session,
                goal,
                proposal,
                [
                    ScheduleRevisionDecisionInput(
                        proposal_item_id=proposal_item.id,
                        decision=ScheduleRevisionDecision.APPROVED,
                        planned_start_date=dt.date(2026, 11, 5),
                    )
                ],
                TODAY,
            )


class TestGetProposalOrRaise:
    def test_returns_the_proposal_when_found(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal = ScheduleRevisionProposal(
            goal_id=goal.id,
            trigger=ScheduleRevisionTrigger.MANUAL,
            status=ScheduleRevisionProposalStatus.PENDING,
        )
        seeded_session.add(proposal)
        seeded_session.flush()

        found = service.get_proposal_or_raise(seeded_session, proposal.id)

        assert found.id == proposal.id

    def test_raises_not_found_for_an_unknown_id(self, seeded_session):
        with pytest.raises(NotFoundError):
            service.get_proposal_or_raise(seeded_session, 999999)


class TestGenerateProposalContextAndErrors:
    def test_zero_items_uses_the_placeholder_text_and_still_calls_ai(
        self, seeded_session, monkeypatch
    ):
        goal = make_exam_goal(seeded_session)
        fake = FakeAi(monkeypatch, ("総評: 作業項目がありません",))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.MANUAL,
            record_date=None,
            today=TODAY,
        )

        assert proposal is None
        assert "作業項目がありません" in fake.sent[0]

    def test_includes_recent_rejections_in_the_prompt(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        old_proposal = ScheduleRevisionProposal(
            goal_id=goal.id,
            trigger=ScheduleRevisionTrigger.AUTO,
            status=ScheduleRevisionProposalStatus.RESOLVED,
        )
        seeded_session.add(old_proposal)
        seeded_session.flush()
        seeded_session.add(
            ScheduleRevisionProposalItem(
                proposal_id=old_proposal.id,
                schedule_item_id=item.id,
                kind=ScheduleRevisionItemKind.CHANGE,
                before_planned_start_date=item.planned_start_date,
                before_planned_end_date=item.planned_end_date,
                before_status=item.status,
                proposed_planned_start_date=dt.date(2026, 11, 22),
                proposed_planned_end_date=dt.date(2026, 11, 23),
                reason="以前の提案",
                decision=ScheduleRevisionDecision.REJECTED,
                reject_reason="まだ早い",
                decided_at=dt.datetime(2026, 11, 24, 0, 0, 0),
            )
        )
        seeded_session.flush()
        fake = FakeAi(monkeypatch, ("総評: 特になし",))

        service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert "まだ早い" in fake.sent[0]

    def test_reading_goal_builds_the_reading_context_stage(self, seeded_session, monkeypatch):
        goal = make_reading_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (_change_block(item.id, "2026-11-26", "2026-12-01"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is not None

    def test_work_goal_builds_the_work_context_stage(self, seeded_session, monkeypatch):
        goal = make_work_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (_change_block(item.id, "2026-11-26", "2026-12-01"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is not None

    def test_raises_ai_auth_required_when_not_authenticated(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        monkeypatch.setattr(ai_client, "is_authenticated", lambda session: False)

        with pytest.raises(AiAuthRequiredError):
            service.generate_proposal(
                seeded_session,
                goal,
                trigger=ScheduleRevisionTrigger.AUTO,
                record_date=TODAY,
                today=TODAY,
            )

    def test_raises_prompt_too_long_when_it_cannot_fit_even_with_entries_emptied(
        self, seeded_session, monkeypatch
    ):
        from app.constants.app_setting_keys import AI_MAX_PROMPT_CHARS
        from tests.schedule_helpers import set_setting

        goal = make_exam_goal(seeded_session)
        make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        set_setting(seeded_session, AI_MAX_PROMPT_CHARS, "1")
        FakeAi(monkeypatch, ("総評: 特になし",))

        with pytest.raises(ScheduleRevisionPromptTooLongError):
            service.generate_proposal(
                seeded_session,
                goal,
                trigger=ScheduleRevisionTrigger.AUTO,
                record_date=TODAY,
                today=TODAY,
            )

    def test_superseding_skips_items_that_are_already_decided(self, seeded_session, monkeypatch):
        """D-65の置き換えは未判断（PENDING）の行だけを対象とする。"""
        goal = make_exam_goal(seeded_session)
        item_a = make_item(
            seeded_session,
            goal,
            title="行A",
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        item_b = make_item(
            seeded_session,
            goal,
            title="行B",
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
            display_order=1,
        )
        response = "\n===\n".join(
            [
                _change_block(item_a.id, "2026-11-26", "2026-12-01"),
                _change_block(item_b.id, "2026-11-27", "2026-12-02"),
            ]
        )
        FakeAi(monkeypatch, (response,))
        first = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )
        first_id = first.id
        item_a_row = next(i for i in first.items if i.schedule_item_id == item_a.id)
        item_b_row = next(i for i in first.items if i.schedule_item_id == item_b.id)
        service.decide(
            seeded_session,
            goal,
            first,
            [
                ScheduleRevisionDecisionInput(
                    proposal_item_id=item_a_row.id, decision=ScheduleRevisionDecision.REJECTED
                )
            ],
            TODAY,
        )
        seeded_session.flush()

        FakeAi(monkeypatch, (_change_block(item_b.id, "2026-11-28", "2026-12-03"),))
        service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.MANUAL,
            record_date=None,
            today=TODAY,
        )

        seeded_session.flush()
        refreshed_a_row = seeded_session.get(ScheduleRevisionProposalItem, item_a_row.id)
        refreshed_b_row = seeded_session.get(ScheduleRevisionProposalItem, item_b_row.id)
        refreshed_first = seeded_session.get(ScheduleRevisionProposal, first_id)
        assert refreshed_a_row.decision == ScheduleRevisionDecision.REJECTED
        assert refreshed_b_row.decision == ScheduleRevisionDecision.SUPERSEDED
        assert refreshed_first.status == ScheduleRevisionProposalStatus.SUPERSEDED


class TestValidateChangesAndWarningsEdgeCases:
    def test_discards_a_change_where_start_is_after_end(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (_change_block(item.id, "2026-12-05", "2026-11-30"),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None

    def test_discards_a_warning_for_another_goals_row(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session, name="目標A")
        other_goal = make_exam_goal(seeded_session, name="目標B")
        make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        other_item = make_item(
            seeded_session,
            other_goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (_warning_block(other_item.id),))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None

    def test_duplicate_warning_blocks_use_only_the_first(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        response = "\n===\n".join(
            [_warning_block(item.id, "最初の理由"), _warning_block(item.id, "2番目の理由")]
        )
        FakeAi(monkeypatch, (response,))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert len(proposal.items) == 1
        assert proposal.items[0].reason == "最初の理由"

    def test_discards_a_warning_with_a_blank_reason(self, seeded_session, monkeypatch):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        FakeAi(monkeypatch, (f"種類: 注意\n行ID: {item.id}\n理由: ",))

        proposal = service.generate_proposal(
            seeded_session,
            goal,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            today=TODAY,
        )

        assert proposal is None


class TestDecideValidationErrors:
    def _make_pending_change_proposal(self, session, goal, item, *, proposed_start, proposed_end):
        proposal = ScheduleRevisionProposal(
            goal_id=goal.id,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            status=ScheduleRevisionProposalStatus.PENDING,
        )
        session.add(proposal)
        session.flush()
        proposal_item = ScheduleRevisionProposalItem(
            proposal_id=proposal.id,
            schedule_item_id=item.id,
            kind=ScheduleRevisionItemKind.CHANGE,
            before_planned_start_date=item.planned_start_date,
            before_planned_end_date=item.planned_end_date,
            before_status=item.status,
            proposed_planned_start_date=proposed_start,
            proposed_planned_end_date=proposed_end,
            reason="遅れています",
            decision=ScheduleRevisionDecision.PENDING,
        )
        session.add(proposal_item)
        session.flush()
        session.refresh(proposal)
        return proposal, proposal_item

    def test_raises_for_an_unknown_proposal_item_id(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal, _proposal_item = self._make_pending_change_proposal(
            seeded_session,
            goal,
            item,
            proposed_start=dt.date(2026, 11, 26),
            proposed_end=dt.date(2026, 12, 1),
        )

        with pytest.raises(ValidationError):
            service.decide(
                seeded_session,
                goal,
                proposal,
                [
                    ScheduleRevisionDecisionInput(
                        proposal_item_id=999999, decision=ScheduleRevisionDecision.APPROVED
                    )
                ],
                TODAY,
            )

    def test_raises_when_the_row_is_already_decided(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal, proposal_item = self._make_pending_change_proposal(
            seeded_session,
            goal,
            item,
            proposed_start=dt.date(2026, 11, 26),
            proposed_end=dt.date(2026, 12, 1),
        )
        proposal_item.decision = ScheduleRevisionDecision.REJECTED
        seeded_session.flush()

        with pytest.raises(ValidationError):
            service.decide(
                seeded_session,
                goal,
                proposal,
                [
                    ScheduleRevisionDecisionInput(
                        proposal_item_id=proposal_item.id,
                        decision=ScheduleRevisionDecision.APPROVED,
                    )
                ],
                TODAY,
            )

    def test_raises_when_acknowledging_a_change_row(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal, proposal_item = self._make_pending_change_proposal(
            seeded_session,
            goal,
            item,
            proposed_start=dt.date(2026, 11, 26),
            proposed_end=dt.date(2026, 12, 1),
        )

        with pytest.raises(ValidationError):
            service.decide(
                seeded_session,
                goal,
                proposal,
                [
                    ScheduleRevisionDecisionInput(
                        proposal_item_id=proposal_item.id,
                        decision=ScheduleRevisionDecision.ACKNOWLEDGED,
                    )
                ],
                TODAY,
            )

    def test_raises_when_approving_a_warning_row(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal = ScheduleRevisionProposal(
            goal_id=goal.id,
            trigger=ScheduleRevisionTrigger.AUTO,
            record_date=TODAY,
            status=ScheduleRevisionProposalStatus.PENDING,
        )
        seeded_session.add(proposal)
        seeded_session.flush()
        proposal_item = ScheduleRevisionProposalItem(
            proposal_id=proposal.id,
            schedule_item_id=item.id,
            kind=ScheduleRevisionItemKind.WARNING,
            before_planned_start_date=item.planned_start_date,
            before_planned_end_date=item.planned_end_date,
            before_status=item.status,
            reason="注意",
            decision=ScheduleRevisionDecision.PENDING,
        )
        seeded_session.add(proposal_item)
        seeded_session.flush()
        seeded_session.refresh(proposal)

        with pytest.raises(ValidationError):
            service.decide(
                seeded_session,
                goal,
                proposal,
                [
                    ScheduleRevisionDecisionInput(
                        proposal_item_id=proposal_item.id,
                        decision=ScheduleRevisionDecision.APPROVED,
                    )
                ],
                TODAY,
            )

    def test_raises_for_an_unsupported_decision_value(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal, proposal_item = self._make_pending_change_proposal(
            seeded_session,
            goal,
            item,
            proposed_start=dt.date(2026, 11, 26),
            proposed_end=dt.date(2026, 12, 1),
        )

        with pytest.raises(ValidationError):
            service.decide(
                seeded_session,
                goal,
                proposal,
                [
                    ScheduleRevisionDecisionInput(
                        proposal_item_id=proposal_item.id, decision=ScheduleRevisionDecision.PENDING
                    )
                ],
                TODAY,
            )

    def test_raises_when_the_override_start_is_after_the_override_end(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal, proposal_item = self._make_pending_change_proposal(
            seeded_session,
            goal,
            item,
            proposed_start=dt.date(2026, 11, 26),
            proposed_end=dt.date(2026, 12, 1),
        )

        with pytest.raises(ValidationError):
            service.decide(
                seeded_session,
                goal,
                proposal,
                [
                    ScheduleRevisionDecisionInput(
                        proposal_item_id=proposal_item.id,
                        decision=ScheduleRevisionDecision.APPROVED,
                        planned_start_date=dt.date(2026, 12, 5),
                        planned_end_date=dt.date(2026, 12, 1),
                    )
                ],
                TODAY,
            )

    def test_raises_when_the_override_end_is_before_today(self, seeded_session):
        goal = make_exam_goal(seeded_session)
        item = make_item(
            seeded_session,
            goal,
            planned_start_date=dt.date(2026, 11, 1),
            planned_end_date=dt.date(2026, 11, 20),
        )
        proposal, proposal_item = self._make_pending_change_proposal(
            seeded_session,
            goal,
            item,
            proposed_start=dt.date(2026, 11, 26),
            proposed_end=dt.date(2026, 12, 1),
        )

        with pytest.raises(ValidationError):
            service.decide(
                seeded_session,
                goal,
                proposal,
                [
                    ScheduleRevisionDecisionInput(
                        proposal_item_id=proposal_item.id,
                        decision=ScheduleRevisionDecision.APPROVED,
                        planned_start_date=dt.date(2026, 11, 10),
                        planned_end_date=dt.date(2026, 11, 20),
                    )
                ],
                TODAY,
            )
