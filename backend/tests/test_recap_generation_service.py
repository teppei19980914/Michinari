"""振り返り（テーマ累積）のAI分類・テーマ本文更新のテスト（AI送信はモックで検証する）。"""

import datetime as dt

import pytest
from sqlalchemy import select

from app.constants.app_setting_keys import AI_MAX_PROMPT_CHARS, RECAP_CLASSIFY_CHUNK_CHARS
from app.models.recap import RecapEntry, RecapTheme
from app.models.setting import AppSetting
from app.services import recap_generation_service, recap_service, record_service
from app.services.exceptions import RecapBodyRejectedError, RecapPromptTooLongError
from tests import reading_helpers
from tests.diary_helpers import finalize_diary, make_exam_goal
from tests.recap_helpers import _all_ids_to, _stub_ai

TODAY = dt.date(2026, 3, 20)


def _set_setting(session, key, value):
    row = session.scalar(select(AppSetting).where(AppSetting.key == key))
    row.value = value
    session.flush()


@pytest.fixture(autouse=True)
def _cleanup_committed_rows(seeded_session):
    """run_all は目標ごとに commit するため、同一DBファイルに残る行を後続テストから消す。"""
    yield
    from app.models.base import Base

    seeded_session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        seeded_session.execute(table.delete())
    seeded_session.commit()


def test_run_for_goal_classifies_entries_and_builds_theme_body(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="SMTPの役割")
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 10), diary_learned="SPFの仕組み")
    _stub_ai(
        monkeypatch,
        classify=_all_ids_to("メール関連"),
        body=lambda m: "## メール関連\n・SMTPの役割（2026-03-09）\n・SPFの仕組み（2026-03-10）",
    )

    count = recap_generation_service.run_for_goal(seeded_session, goal, TODAY)

    theme = seeded_session.scalar(select(RecapTheme).where(RecapTheme.goal_id == goal.id))
    assert count == 2
    assert theme.name == "メール関連"
    assert "SPFの仕組み" in theme.body
    pending = seeded_session.scalars(
        select(RecapEntry).where(RecapEntry.classified_at.is_(None))
    ).all()
    assert pending == []


def test_run_for_goal_passes_existing_body_to_the_next_update(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="SMTP")
    calls = _stub_ai(monkeypatch, classify=_all_ids_to("メール関連"), body=lambda m: "・SMTP")
    recap_generation_service.run_for_goal(seeded_session, goal, TODAY)
    seeded_session.commit()
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 10), diary_learned="SPF")
    seeded_session.commit()

    recap_generation_service.run_for_goal(seeded_session, goal, TODAY)

    body_calls = [m for m in calls if "統合の規則" in m]
    assert "・SMTP" in body_calls[-1]
    assert "SPF" in body_calls[-1]


def test_shorter_body_is_rejected_and_unregistered_entries_are_retried(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="SMTP")
    long_body = "・" + "詳細な本文" * 20
    _stub_ai(monkeypatch, classify=_all_ids_to("メール関連"), body=lambda m: long_body)
    recap_generation_service.run_for_goal(seeded_session, goal, TODAY)
    seeded_session.commit()
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 10), diary_learned="SPF")
    seeded_session.commit()
    _stub_ai(monkeypatch, classify=_all_ids_to("メール関連"), body=lambda m: "短い")

    with pytest.raises(RecapBodyRejectedError):
        recap_generation_service.run_for_goal(seeded_session, goal, TODAY)
    seeded_session.rollback()

    theme = seeded_session.scalar(select(RecapTheme).where(RecapTheme.goal_id == goal.id))
    assert theme.body == long_body
    # 報告の登録（未分類の状態）はAI呼び出し前に確定しており残る。分類と本文統合は取り消される
    assert seeded_session.query(RecapEntry).count() == 2
    assert seeded_session.query(RecapEntry).filter(RecapEntry.classified_at.is_(None)).count() == 1

    _stub_ai(monkeypatch, classify=_all_ids_to("メール関連"), body=lambda m: long_body + "\n・SPF")
    assert recap_generation_service.run_for_goal(seeded_session, goal, TODAY) == 1


def test_empty_theme_body_response_is_rejected(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="SMTP")
    _stub_ai(monkeypatch, classify=_all_ids_to("メール関連"), body=lambda m: "   ")

    with pytest.raises(RecapBodyRejectedError):
        recap_generation_service.run_for_goal(seeded_session, goal, TODAY)


def test_prompt_exceeding_limit_is_not_sent(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="SMTP")
    _set_setting(seeded_session, AI_MAX_PROMPT_CHARS, "100")
    calls = _stub_ai(monkeypatch, classify=_all_ids_to("A"), body=lambda m: "x")

    with pytest.raises(RecapPromptTooLongError):
        recap_generation_service.run_for_goal(seeded_session, goal, TODAY)
    assert calls == []


def test_entries_are_split_into_multiple_classification_calls(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    for day in (9, 10, 11):
        finalize_diary(seeded_session, goal, dt.date(2026, 3, day), diary_learned="あ" * 20)
    _set_setting(seeded_session, RECAP_CLASSIFY_CHUNK_CHARS, "30")
    calls = _stub_ai(monkeypatch, classify=_all_ids_to("A"), body=lambda m: "・本文")

    recap_generation_service.run_for_goal(seeded_session, goal, TODAY)

    assert len([m for m in calls if "既存のテーマ（" in m]) == 3


def test_entries_without_response_stay_pending_for_next_run(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, dt.date(2026, 3, 9), diary_learned="SMTP")
    _stub_ai(monkeypatch, classify=lambda m: "応答形式が違う", body=lambda m: "x")

    count = recap_generation_service.run_for_goal(seeded_session, goal, TODAY)

    assert count == 0
    assert seeded_session.query(RecapTheme).count() == 0


def test_today_entries_are_excluded_from_the_batch(seeded_session, monkeypatch):
    goal = make_exam_goal(seeded_session)
    finalize_diary(seeded_session, goal, TODAY, diary_learned="今日の学び")
    _stub_ai(monkeypatch, classify=_all_ids_to("A"), body=lambda m: "x")

    assert recap_generation_service.run_for_goal(seeded_session, goal, TODAY) == 0


def test_reading_goal_recalls_are_classified_into_themes(seeded_session, monkeypatch):
    goal = reading_helpers.make_reading_goal(seeded_session, name="読書目標")
    book = reading_helpers.make_book(seeded_session, goal.id)
    record_service.finalize_reading_record(
        seeded_session,
        dt.date(2026, 3, 9),
        [reading_helpers.reading_log_item(book.id, recall_body="ネットワークの層構造")],
        dt.date(2026, 3, 9),
    )
    _stub_ai(monkeypatch, classify=_all_ids_to("通信"), body=lambda m: "・ネットワークの層構造")

    count = recap_generation_service.run_for_goal(seeded_session, goal, TODAY)

    theme = seeded_session.scalar(select(RecapTheme).where(RecapTheme.goal_id == goal.id))
    assert count == 1
    assert theme.name == "通信"


def test_run_all_isolates_failures_per_goal(seeded_session, monkeypatch):
    failing = make_exam_goal(seeded_session, name="失敗する目標")
    working = make_exam_goal(seeded_session, name="成功する目標")
    finalize_diary(seeded_session, working, dt.date(2026, 3, 9), diary_learned="SMTP")
    seeded_session.commit()
    original = recap_generation_service.run_for_goal

    def _fail_for_one(session, goal, today):
        if goal.id == failing.id:
            raise RecapBodyRejectedError("強制失敗")
        return original(session, goal, today)

    _stub_ai(monkeypatch, classify=_all_ids_to("A"), body=lambda m: "・本文")
    monkeypatch.setattr(recap_generation_service, "run_for_goal", _fail_for_one)

    total = recap_generation_service.run_all(seeded_session, TODAY)

    assert total == 1
    assert seeded_session.query(RecapTheme).count() == 1


def test_run_all_with_no_goals_returns_zero(seeded_session):
    assert recap_generation_service.run_all(seeded_session, TODAY) == 0


def test_entry_texts_of_empty_list_is_empty(seeded_session):
    assert recap_service.entry_texts(seeded_session, []) == []
