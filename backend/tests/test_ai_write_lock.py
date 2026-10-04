"""AI通信中に書き込みロックを保持しないことの回帰テスト（SQLite「database is locked」対策）。

2026-10-04の実機障害：起動時の振り返りバッチが、書き込みトランザクションを保持したまま
AIを連続呼び出ししている間、月次報告の生成がロックを取れず30秒後に失敗した。ここでは実際の
一時ファイルDBを使い、AI応答の待機中に別接続から書き込み（BEGIN IMMEDIATE）できることを確かめる。
"""

import datetime as dt
import sqlite3

from sqlalchemy import select

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.constants.app_setting_keys import RECAP_CLASSIFY_CHUNK_CHARS
from app.constants.enums import ConversationScope, GoalCategory, GoalStatus, RecordState
from app.database import SessionLocal, engine
from app.models.ai import AiConversation, AiLog
from app.models.goal import Goal
from app.models.recap import RecapEntry, RecapTheme
from app.models.record import DailyRecord, WorkLog
from app.models.retrospective import GoalRetrospective
from app.models.setting import AppSetting
from app.models.work import WorkAssignment
from app.services import recap_generation_service, work_report_service
from app.services.exceptions import RecapBodyRejectedError
from tests.diary_helpers import finalize_diary, make_exam_goal
from tests.recap_helpers import _all_ids_to

TODAY = dt.date(2026, 3, 20)

_MONTHLY_RESPONSE = (
    "## 業務内容の要約\n業務\n\n## 達成度\n3\n\n"
    "## 達成状況の振り返り\n振り返り\n\n## 来月の目標\n次月\n\n## 報告・連絡事項\nなし\n"
)
_LONG_BODY = "・" + "詳細な本文" * 5


def _write_lock_is_free() -> bool:
    """別接続で書き込みロックを取れるかを確かめる（取れなければ他の書き込みが待たされる）。"""
    connection = sqlite3.connect(engine.url.database, timeout=0.2)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        connection.close()


class _ProbingAi:
    """AI呼び出しのたびに書き込みロックの空きを記録する。応答は本文の種類で振り分ける。"""

    def __init__(self, respond, on_call=None):
        self.lock_free_at_call: list[bool] = []
        self._respond = respond
        self._on_call = on_call

    def __call__(self, session, *, chat_uid, message):
        self.lock_free_at_call.append(_write_lock_is_free())
        if self._on_call is not None:
            self._on_call(message)
        return ai_client.SendResult(response_text=self._respond(message), latency_ms=1)


def _install_ai(monkeypatch, fake):
    monkeypatch.setattr(ai_client, "send_message", fake)
    counter = iter(range(1000))
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: f"chat-{next(counter)}",
    )
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _respond_recap(message):
    if "既存のテーマ（" in message:
        return _all_ids_to("メール関連")(message)
    if "統合の規則" in message:
        return "・本文"
    return _MONTHLY_RESPONSE


def _set_chunk_budget(session, value):
    row = session.scalar(select(AppSetting).where(AppSetting.key == RECAP_CLASSIFY_CHUNK_CHARS))
    row.value = value
    session.commit()


def _make_work_goal(session, name="仕事目標A"):
    goal = Goal(
        category=GoalCategory.WORK,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_work_assignment(session, goal):
    assignment = WorkAssignment(
        goal_id=goal.id, expected_content="想定業務内容", start_date=dt.date(2026, 1, 1)
    )
    session.add(assignment)
    session.flush()
    return assignment


def _add_work_log(session, work_assignment_id, record_date):
    record = DailyRecord(record_date=record_date, work_record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    session.add(
        WorkLog(daily_record_id=record.id, work_assignment_id=work_assignment_id, body="業務")
    )
    session.flush()


def test_recap_batch_does_not_hold_write_lock_during_ai_calls(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="SMTP")
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 10), diary_learned="SPF")
    seeded_session.commit()
    fake = _ProbingAi(_respond_recap)
    _install_ai(monkeypatch, fake)

    recap_generation_service.run_for_goal(seeded_session, goal, TODAY)

    assert len(fake.lock_free_at_call) == 2
    assert all(fake.lock_free_at_call)


def test_monthly_report_is_generated_while_recap_batch_is_running(seeded_session, monkeypatch):
    """起動時バッチの途中で月次報告を生成しても失敗しない（2026-10-04の障害の再現条件）。"""
    exam = make_exam_goal(seeded_session, name="資格目標")
    finalize_diary(seeded_session, exam, dt.date(2026, 3, 9), diary_learned="SMTP")
    work = _make_work_goal(seeded_session)
    assignment = _make_work_assignment(seeded_session, work)
    _add_work_log(seeded_session, assignment.id, dt.date(2026, 9, 10))
    seeded_session.commit()
    work_id = work.id
    generated = {}

    def _generate_monthly_from_another_session(message):
        if "既存のテーマ（" not in message:
            return
        if generated:
            return
        other = SessionLocal()
        try:
            report = work_report_service.generate_monthly_report(
                other,
                other.get(Goal, work_id),
                period_key="2026-09",
                today=dt.date(2026, 10, 4),
            )
            other.commit()
            generated["period_key"] = report.period_key
        finally:
            other.close()

    _install_ai(
        monkeypatch, _ProbingAi(_respond_recap, on_call=_generate_monthly_from_another_session)
    )

    recap_generation_service.run_all(seeded_session, TODAY)

    assert generated == {"period_key": "2026-09"}
    check = SessionLocal()
    try:
        saved = check.scalar(
            select(GoalRetrospective).where(
                GoalRetrospective.goal_id == work_id, GoalRetrospective.period_key == "2026-09"
            )
        )
        assert saved is not None
    finally:
        check.close()


def test_monthly_report_generation_does_not_hold_write_lock_during_ai_call(
    seeded_session, monkeypatch
):
    work = _make_work_goal(seeded_session)
    assignment = _make_work_assignment(seeded_session, work)
    _add_work_log(seeded_session, assignment.id, dt.date(2026, 9, 10))
    seeded_session.commit()
    fake = _ProbingAi(_respond_recap)
    _install_ai(monkeypatch, fake)

    work_report_service.generate_monthly_report(
        seeded_session, work, period_key="2026-09", today=dt.date(2026, 10, 4)
    )

    assert fake.lock_free_at_call == [True]


def test_rebuild_theme_does_not_hold_write_lock_during_ai_calls(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="SMTP")
    seeded_session.commit()
    _install_ai(monkeypatch, _ProbingAi(_respond_recap))
    recap_generation_service.run_for_goal(seeded_session, goal, TODAY)
    seeded_session.commit()
    theme = seeded_session.scalar(select(RecapTheme).where(RecapTheme.goal_id == goal.id))
    # 会話行が既にあると新規作成（書き込み）が起きないため、無い状態で再構築させる
    seeded_session.query(AiConversation).delete()
    seeded_session.commit()
    fake = _ProbingAi(_respond_recap)
    _install_ai(monkeypatch, fake)

    recap_generation_service.rebuild_theme(seeded_session, goal, theme)

    assert fake.lock_free_at_call and all(fake.lock_free_at_call)


def test_failed_recap_chunk_keeps_earlier_chunks_and_leaves_its_entries_pending(
    seeded_session, monkeypatch
):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="あ" * 20)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 10), diary_learned="い" * 20)
    _set_chunk_budget(seeded_session, "30")
    bodies = iter([_LONG_BODY, "短い"])

    def _respond(message):
        if "既存のテーマ（" in message:
            return _all_ids_to("メール関連")(message)
        return next(bodies)

    _install_ai(monkeypatch, _ProbingAi(_respond))

    try:
        recap_generation_service.run_for_goal(seeded_session, goal, TODAY)
    except RecapBodyRejectedError:
        seeded_session.rollback()
    else:  # pragma: no cover - 2件目の本文は縮みすぎとして必ず拒否される
        raise AssertionError("2件目のチャンクは拒否されるはず")

    theme = seeded_session.scalar(select(RecapTheme).where(RecapTheme.goal_id == goal.id))
    assert theme.body == _LONG_BODY
    assert seeded_session.query(RecapEntry).filter(RecapEntry.classified_at.is_(None)).count() == 1
    assert (
        seeded_session.query(RecapEntry).filter(RecapEntry.classified_at.isnot(None)).count() == 1
    )


def test_recap_scope_key_uses_theme_name_before_theme_exists_then_theme_id(
    seeded_session, monkeypatch
):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="SMTP")
    seeded_session.commit()
    _install_ai(monkeypatch, _ProbingAi(_respond_recap))
    recap_generation_service.run_for_goal(seeded_session, goal, TODAY)
    seeded_session.commit()
    theme = seeded_session.scalar(select(RecapTheme).where(RecapTheme.goal_id == goal.id))
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 10), diary_learned="SPF")
    seeded_session.commit()

    recap_generation_service.run_for_goal(seeded_session, goal, TODAY)

    keys = set(
        seeded_session.scalars(
            select(AiConversation.scope_key).where(
                AiConversation.goal_id == goal.id,
                AiConversation.scope == ConversationScope.RECAP,
                AiConversation.scope_key.like("theme%"),
            )
        ).all()
    )
    assert keys == {"theme-name-メール関連", f"theme-{theme.id}"}


def test_send_and_log_and_conversation_are_committed_before_returning(seeded_session, monkeypatch):
    """AI応答後の通信記録と、AI呼び出し前の会話行は、別セッションから見えること。"""
    work = _make_work_goal(seeded_session)
    assignment = _make_work_assignment(seeded_session, work)
    _add_work_log(seeded_session, assignment.id, dt.date(2026, 9, 10))
    seeded_session.commit()
    seen_conversations = []

    def _check_committed(message):
        other = SessionLocal()
        try:
            seen_conversations.append(other.query(AiConversation).count())
        finally:
            other.close()

    _install_ai(monkeypatch, _ProbingAi(_respond_recap, on_call=_check_committed))

    work_report_service.generate_monthly_report(
        seeded_session, work, period_key="2026-09", today=dt.date(2026, 10, 4)
    )

    assert seen_conversations == [1]
    check = SessionLocal()
    try:
        assert check.query(AiLog).count() == 1
        assert check.query(AiConversation).count() == 1
    finally:
        check.close()
