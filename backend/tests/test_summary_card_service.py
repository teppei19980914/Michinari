"""ふりかえりまとめ・共有カードの集計・AI一文生成のテスト（開発Todo「まとめと共有カード」
v1.0 §4・§6）。

実際のAI基盤へは接続せず、`tests.ai_chat_fakes.FakeAi`でapp.ai.clientの通信関数を
差し替えて検証する（ヘルプAIアシスタント・目標相談チャットと同じ方針）。
"""

import datetime as dt

import pytest

from app.ai import rate_limiter
from app.ai.exceptions import AiAuthRequiredError
from app.constants.enums import (
    GoalCategory,
    GoalStatus,
    MilestoneType,
    RecapSourceKind,
    RecordState,
)
from app.models.book import Book
from app.models.goal import Goal
from app.models.milestone import GoalMilestoneAchievement
from app.models.recap import RecapEntry, RecapTheme, RecapThemeLink
from app.models.record import DailyRecord, ReadingLog, WorkLog
from app.models.work import WorkAssignment
from app.services import summary_card_service as service
from app.services.exceptions import ValidationError
from tests.ai_chat_fakes import FakeAi

_START = dt.date(2026, 1, 1)
_FROM = dt.date(2026, 1, 1)
_TO = dt.date(2026, 1, 31)


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


def _make_exam_goal(session, *, start_date=_START):
    goal = Goal(name="資格目標A", start_date=start_date, status=GoalStatus.ACTIVE)
    session.add(goal)
    session.flush()
    return goal


def _make_reading_goal(session, *, start_date=_START):
    goal = Goal(
        category=GoalCategory.READING,
        name="読書目標A",
        start_date=start_date,
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_work_goal(session, *, start_date=_START):
    goal = Goal(
        category=GoalCategory.WORK,
        name="仕事目標A",
        start_date=start_date,
        status=GoalStatus.ACTIVE,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_exam_record(session, record_date, state=RecordState.REPORTED):
    record = DailyRecord(record_date=record_date, exam_record_state=state)
    session.add(record)
    session.flush()
    return record


def _make_reading_record(session, record_date, state=RecordState.REPORTED):
    record = DailyRecord(record_date=record_date, reading_record_state=state)
    session.add(record)
    session.flush()
    return record


def _make_work_record(session, record_date, state=RecordState.REPORTED):
    record = DailyRecord(record_date=record_date, work_record_state=state)
    session.add(record)
    session.flush()
    return record


def _add_theme_entry(
    session, goal, theme_name: str, record_date: dt.date, source_id: int, *, source_kind
):
    theme = session.query(RecapTheme).filter_by(goal_id=goal.id, name=theme_name).one_or_none()
    if theme is None:
        theme = RecapTheme(goal_id=goal.id, name=theme_name, body="")
        session.add(theme)
        session.flush()
    entry = RecapEntry(
        goal_id=goal.id,
        source_kind=source_kind,
        source_id=source_id,
        record_date=record_date,
        classified_at=dt.datetime(2026, 1, 1),
    )
    session.add(entry)
    session.flush()
    session.add(RecapThemeLink(theme_id=theme.id, entry_id=entry.id))
    session.commit()
    return theme


# --- get_summary ---


def test_get_summary_rejects_from_after_to(seeded_session):
    goal = _make_exam_goal(seeded_session)

    with pytest.raises(ValidationError):
        service.get_summary(
            seeded_session, goal, date_from=dt.date(2026, 1, 10), date_to=dt.date(2026, 1, 1)
        )


def test_get_summary_counts_record_days_and_longest_streak(seeded_session):
    goal = _make_exam_goal(seeded_session)
    for day in range(1, 4):
        _make_exam_record(seeded_session, dt.date(2026, 1, day))
    seeded_session.commit()

    summary = service.get_summary(seeded_session, goal, date_from=_FROM, date_to=_TO)

    assert summary.record_days == 3
    assert summary.longest_consecutive_days == 3


def test_get_summary_top_theme_name_picks_most_frequent_theme_in_period(seeded_session):
    goal = _make_exam_goal(seeded_session)
    # 最初に作る（updated_at最古=反復順で最後に評価される）、件数の少ないテーマ。
    # best_countが既に更新済みの状態で評価され、更新しない分岐（count > best_countがFalse）を
    # 通ることを確かめる。
    _add_theme_entry(
        seeded_session, goal, "テーマC", dt.date(2026, 1, 20), 0, source_kind=RecapSourceKind.DIARY
    )
    _add_theme_entry(
        seeded_session, goal, "テーマA", dt.date(2026, 1, 5), 1, source_kind=RecapSourceKind.DIARY
    )
    _add_theme_entry(
        seeded_session, goal, "テーマA", dt.date(2026, 1, 6), 2, source_kind=RecapSourceKind.DIARY
    )
    _add_theme_entry(
        seeded_session, goal, "テーマB", dt.date(2026, 1, 7), 3, source_kind=RecapSourceKind.DIARY
    )
    # 期間外の記録（テーマBが期間内で逆転しないことの検証）
    _add_theme_entry(
        seeded_session, goal, "テーマB", dt.date(2026, 2, 1), 4, source_kind=RecapSourceKind.DIARY
    )

    summary = service.get_summary(seeded_session, goal, date_from=_FROM, date_to=_TO)

    assert summary.top_theme_name == "テーマA"


def test_get_summary_top_theme_name_is_none_when_no_theme_entries(seeded_session):
    goal = _make_exam_goal(seeded_session)

    summary = service.get_summary(seeded_session, goal, date_from=_FROM, date_to=_TO)

    assert summary.top_theme_name is None


def test_get_summary_top_theme_name_is_none_for_work_goal(seeded_session):
    goal = _make_work_goal(seeded_session)

    summary = service.get_summary(seeded_session, goal, date_from=_FROM, date_to=_TO)

    assert summary.top_theme_name is None


def test_get_summary_includes_only_milestones_achieved_within_period(seeded_session):
    goal = _make_exam_goal(seeded_session)
    seeded_session.add(
        GoalMilestoneAchievement(
            goal_id=goal.id,
            milestone_type=MilestoneType.CONSECUTIVE_DAYS,
            milestone_key="3",
            achieved_at=dt.datetime(2026, 1, 10),
        )
    )
    seeded_session.add(
        GoalMilestoneAchievement(
            goal_id=goal.id,
            milestone_type=MilestoneType.CONSECUTIVE_DAYS,
            milestone_key="7",
            achieved_at=dt.datetime(2026, 2, 10),
        )
    )
    seeded_session.commit()

    summary = service.get_summary(seeded_session, goal, date_from=_FROM, date_to=_TO)

    assert [m.milestone_key for m in summary.milestones] == ["3"]


def test_get_summary_roadmap_fields_are_present(seeded_session):
    goal = _make_exam_goal(seeded_session)

    summary = service.get_summary(seeded_session, goal, date_from=_FROM, date_to=_TO)

    assert isinstance(summary.roadmap.progress_ratio, float)
    assert isinstance(summary.roadmap.is_achieved, bool)


# --- generate_sentence ---


def test_generate_sentence_requires_ai_connection(seeded_session, monkeypatch):
    from app.ai import client as ai_client

    monkeypatch.setattr(ai_client, "is_authenticated", lambda session: False)
    goal = _make_exam_goal(seeded_session)

    with pytest.raises(AiAuthRequiredError):
        service.generate_sentence(seeded_session, goal, date_from=_FROM, date_to=_TO)


def test_generate_sentence_rejects_from_after_to(seeded_session, monkeypatch):
    FakeAi(monkeypatch, ("一文です。",))
    goal = _make_exam_goal(seeded_session)

    with pytest.raises(ValidationError):
        service.generate_sentence(
            seeded_session, goal, date_from=dt.date(2026, 1, 10), date_to=dt.date(2026, 1, 1)
        )


def test_generate_sentence_exam_sends_anonymize_instruction_and_discards_chat(
    seeded_session, monkeypatch
):
    goal = _make_exam_goal(seeded_session)
    fake = FakeAi(monkeypatch, ("積み重ねた努力が伝わる一文です。",))

    sentence = service.generate_sentence(seeded_session, goal, date_from=_FROM, date_to=_TO)

    assert sentence == "積み重ねた努力が伝わる一文です。"
    assert len(fake.sent) == 1
    assert "匿名化の指示" in fake.sent[0]
    assert "要約・一般化した新しい一文" in fake.sent[0]
    assert fake.deleted == fake.created  # 送信後に必ず削除される（28.5）


def test_generate_sentence_reading_with_book_and_recall(seeded_session, monkeypatch):
    goal = _make_reading_goal(seeded_session)
    book = Book(
        goal_id=goal.id,
        title="書籍A",
        total_pages=200,
        start_date=_START,
        due_date=dt.date(2026, 6, 1),
    )
    seeded_session.add(book)
    seeded_session.flush()
    record = _make_reading_record(seeded_session, dt.date(2026, 1, 5))
    seeded_session.add(
        ReadingLog(daily_record_id=record.id, book_id=book.id, recall_body="第3章を読んだ。")
    )
    seeded_session.commit()
    fake = FakeAi(monkeypatch, ("読書の積み重ねが伝わる一文です。",))

    sentence = service.generate_sentence(seeded_session, goal, date_from=_FROM, date_to=_TO)

    assert sentence == "読書の積み重ねが伝わる一文です。"
    assert fake.deleted == fake.created


def test_generate_sentence_reading_without_book_sends_empty_records(seeded_session, monkeypatch):
    goal = _make_reading_goal(seeded_session)
    fake = FakeAi(monkeypatch, ("一文です。",))

    service.generate_sentence(seeded_session, goal, date_from=_FROM, date_to=_TO)

    assert "対象期間に記録はありません" in fake.sent[0]


def test_generate_sentence_work_with_assignment_and_log(seeded_session, monkeypatch):
    goal = _make_work_goal(seeded_session)
    work_assignment = WorkAssignment(
        goal_id=goal.id, expected_content="想定業務内容", start_date=_START
    )
    seeded_session.add(work_assignment)
    seeded_session.flush()
    record = _make_work_record(seeded_session, dt.date(2026, 1, 5))
    seeded_session.add(
        WorkLog(
            daily_record_id=record.id, work_assignment_id=work_assignment.id, body="案件Aを進めた。"
        )
    )
    seeded_session.commit()
    fake = FakeAi(monkeypatch, ("仕事の積み重ねが伝わる一文です。",))

    sentence = service.generate_sentence(seeded_session, goal, date_from=_FROM, date_to=_TO)

    assert sentence == "仕事の積み重ねが伝わる一文です。"
    assert fake.deleted == fake.created


def test_generate_sentence_work_without_assignment_sends_empty_records(seeded_session, monkeypatch):
    goal = _make_work_goal(seeded_session)
    fake = FakeAi(monkeypatch, ("一文です。",))

    service.generate_sentence(seeded_session, goal, date_from=_FROM, date_to=_TO)

    assert "対象期間に記録はありません" in fake.sent[0]
