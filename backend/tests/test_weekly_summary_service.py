"""weekly_summary_service のテスト（ロジック・プロンプト編15章・17.3、
実装フェーズ分割計画書Phase5完了条件「週次要約が起動時に遡及生成される」
「遡及生成時に呼び出し間隔の下限が守られる」）。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.ai.exceptions import AiError
from app.constants.enums import GoalStatus, QualityMetricType
from app.models.ai import AiConversation, AiLog
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, StudyLog, WeeklySummary
from app.services import weekly_summary_service
from app.services.weekly_summary_service import _last_completed_sunday
from tests import reading_helpers


def _make_goal(session, name="目標A"):
    goal = Goal(name=name, start_date=dt.date(2026, 1, 1), status=GoalStatus.ACTIVE)
    session.add(goal)
    session.flush()
    return goal


def _make_material(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        name="教材A",
        unit_label="ページ",
        total_amount=100.0,
        planned_cycles=1,
        start_date=dt.date(2026, 1, 1),
        due_date=dt.date(2026, 12, 31),
        quality_metric_type=QualityMetricType.NONE,
        display_order=1,
    )
    defaults.update(overrides)
    material = Material(**defaults)
    session.add(material)
    session.flush()
    return material


def _make_daily_record_with_log(session, material, record_date, **overrides):
    record = DailyRecord(record_date=record_date, exam_record_state="REPORTED")
    session.add(record)
    session.flush()
    defaults = dict(
        daily_record_id=record.id,
        material_id=material.id,
        minutes_spent=30,
        amount_completed=10.0,
        cycle_number=1,
    )
    defaults.update(overrides)
    session.add(StudyLog(**defaults))
    session.flush()
    return record


def _stub_send_message(monkeypatch, *, response="週次要約の本文", raise_exc_for=None):
    """raise_exc_for: 例外を発生させたいchat_uidの集合（省略時は常に成功）。"""
    calls = []

    def _fake(session, *, chat_uid, message):
        calls.append({"chat_uid": chat_uid, "message": message})
        if raise_exc_for and chat_uid in raise_exc_for:
            raise AiError("通信に失敗しました")
        return ai_client.SendResult(response_text=response, latency_ms=10)

    monkeypatch.setattr(ai_client, "send_message", _fake)
    counter = iter(range(1000))
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: f"chat-{next(counter)}",
    )
    return calls


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep_by_default(monkeypatch):
    """個別のテストで明示的に検証しない限り、実sleepでテストを遅くしない。"""
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _cleanup_committed_rows(seeded_session):
    """run_retroactive_generationは週ごとにcommit/rollbackする設計（16.7の失敗分離のため、
    他のサービスと異なり内部でcommitする）。db_sessionフィクスチャのrollbackだけでは
    committed行が同一DBファイルに残り後続テストを汚染するため、明示的に全テーブルを空にする
    （tests/conftest.pyのclientフィクスチャと同じ後始末パターン）。
    """
    yield
    from app.models.base import Base

    seeded_session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        seeded_session.execute(table.delete())
    seeded_session.commit()


# --- _last_completed_sunday ---


def test_last_completed_sunday_returns_self_when_today_is_sunday():
    sunday = dt.date(2026, 8, 23)
    assert sunday.weekday() == 6
    assert _last_completed_sunday(sunday) == sunday


def test_last_completed_sunday_returns_previous_sunday_mid_week():
    wednesday = dt.date(2026, 8, 26)
    assert _last_completed_sunday(wednesday) == dt.date(2026, 8, 23)


# --- list_pending_weeks ---


def test_list_pending_weeks_finds_goal_with_logs_in_completed_week(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))  # 火曜

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24), lookback_weeks=4
    )

    assert len(pending) == 1
    assert pending[0].goal.id == goal.id
    assert pending[0].week_start == dt.date(2026, 8, 17)
    assert pending[0].week_end == dt.date(2026, 8, 23)


def test_list_pending_weeks_excludes_reading_goals(seeded_session):
    """読書目標（category=READING）はstudy_logを持たないため、reading_logがあっても
    週次要約の生成対象から自動的に除外されエラーも起きないこと（ロジック・プロンプト編21.1、
    実装フェーズ分割計画書Phase16完了条件）。
    """
    from app.constants.enums import GoalCategory, RecordState
    from app.models.record import ReadingLog

    reading_goal = Goal(
        category=GoalCategory.READING,
        name="読書目標A",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    seeded_session.add(reading_goal)
    seeded_session.flush()
    book = reading_helpers.make_book(seeded_session, reading_goal.id)
    record = DailyRecord(
        record_date=dt.date(2026, 8, 18), reading_record_state=RecordState.PROGRESS_ONLY
    )
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        ReadingLog(daily_record_id=record.id, book_id=book.id, recall_body="想起本文")
    )
    seeded_session.flush()

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24), lookback_weeks=4
    )

    assert pending == []


def test_list_pending_weeks_excludes_work_goals(seeded_session):
    """仕事目標（category=WORK）はstudy_logを持たないため、work_logがあっても
    週次要約の生成対象から自動的に除外されエラーも起きないこと（読書と同じ理由。
    実装フェーズ分割計画書Phase22回帰防止観点）。
    """
    from app.constants.enums import GoalCategory, RecordState
    from app.models.record import WorkLog
    from app.models.work import WorkAssignment

    work_goal = Goal(
        category=GoalCategory.WORK,
        name="仕事目標A",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    seeded_session.add(work_goal)
    seeded_session.flush()
    work_assignment = WorkAssignment(
        goal_id=work_goal.id, expected_content="想定業務内容", start_date=dt.date(2026, 1, 1)
    )
    seeded_session.add(work_assignment)
    seeded_session.flush()
    record = DailyRecord(
        record_date=dt.date(2026, 8, 18), work_record_state=RecordState.PROGRESS_ONLY
    )
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        WorkLog(daily_record_id=record.id, work_assignment_id=work_assignment.id, body="業務内容")
    )
    seeded_session.flush()

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24), lookback_weeks=4
    )

    assert pending == []


def test_list_pending_weeks_excludes_already_generated(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))
    seeded_session.add(
        WeeklySummary(
            goal_id=goal.id,
            week_start_date=dt.date(2026, 8, 17),
            week_end_date=dt.date(2026, 8, 23),
            summary_body="既に生成済み",
        )
    )
    seeded_session.flush()

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24), lookback_weeks=4
    )

    assert pending == []


def test_list_pending_weeks_excludes_weeks_without_logs(seeded_session):
    _make_goal(seeded_session)

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24), lookback_weeks=4
    )

    assert pending == []


def test_list_pending_weeks_respects_lookback_limit(seeded_session):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    # 5週間前（lookback=4の範囲外）の実績のみ
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 7, 21))

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24), lookback_weeks=4
    )

    assert pending == []


# --- generate_for_week ---


def test_generate_for_week_raises_when_prompt_template_missing(seeded_session):
    from app.constants.enums import AiPurpose
    from app.models.setting import PromptTemplate
    from app.services.exceptions import ValidationError

    goal = _make_goal(seeded_session)
    seeded_session.query(PromptTemplate).filter_by(purpose=AiPurpose.WEEKLY_SUMMARY.value).delete()
    seeded_session.flush()

    with pytest.raises(ValidationError):
        weekly_summary_service.generate_for_week(
            seeded_session, goal, week_start=dt.date(2026, 8, 17), week_end=dt.date(2026, 8, 23)
        )


def test_generate_for_week_creates_summary_and_logs_call(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))
    _stub_send_message(monkeypatch)

    summary = weekly_summary_service.generate_for_week(
        seeded_session, goal, week_start=dt.date(2026, 8, 17), week_end=dt.date(2026, 8, 23)
    )

    assert summary.goal_id == goal.id
    assert summary.summary_body == "週次要約の本文"
    assert seeded_session.query(AiLog).count() == 1
    # last_parent_orderの更新はai/orchestration.send_and_logに共通化されており、
    # 週次要約でも成功時に更新されることを確認する（リファクタ前の片手落ちの回帰防止）。
    conversation = seeded_session.query(AiConversation).one()
    assert conversation.last_parent_order == 1


# --- run_retroactive_generation ---


def test_run_retroactive_generation_creates_pending_summaries(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))
    _stub_send_message(monkeypatch)

    generated = weekly_summary_service.run_retroactive_generation(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert generated == 1
    assert seeded_session.query(WeeklySummary).count() == 1


def test_run_retroactive_generation_continues_after_one_failure(seeded_session, monkeypatch):
    goal_a = _make_goal(seeded_session, name="目標A")
    goal_b = _make_goal(seeded_session, name="目標B")
    material_a = _make_material(seeded_session, goal_a)
    material_b = _make_material(seeded_session, goal_b)
    _make_daily_record_with_log(seeded_session, material_a, dt.date(2026, 8, 18))
    _make_daily_record_with_log(seeded_session, material_b, dt.date(2026, 8, 19))
    # run_retroactive_generationは1件ごとにcommit/rollbackする（16.7の失敗分離）ため、
    # フィクスチャのセットアップは先にcommitしておく。そうしないと1件目の失敗時の
    # rollbackで2件目用の未コミットデータまで消えてしまう。
    seeded_session.commit()
    # 最初に作られる会話（chat-0）だけ失敗させ、もう一方（chat-1）は成功させる。
    _stub_send_message(monkeypatch, raise_exc_for={"chat-0"})

    generated = weekly_summary_service.run_retroactive_generation(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert generated == 1
    assert seeded_session.query(WeeklySummary).count() == 1
    # 失敗した側のエラーもai_logへ記録されている（コミット済みの成功分とは別トランザクション）。
    error_logs = seeded_session.query(AiLog).filter(AiLog.error_type.isnot(None)).all()
    assert len(error_logs) == 1


def test_run_retroactive_generation_respects_call_interval(seeded_session, monkeypatch):
    goal_a = _make_goal(seeded_session, name="目標A")
    goal_b = _make_goal(seeded_session, name="目標B")
    material_a = _make_material(seeded_session, goal_a)
    material_b = _make_material(seeded_session, goal_b)
    _make_daily_record_with_log(seeded_session, material_a, dt.date(2026, 8, 18))
    _make_daily_record_with_log(seeded_session, material_b, dt.date(2026, 8, 19))
    seeded_session.commit()
    _stub_send_message(monkeypatch)

    wait_calls = []
    monkeypatch.setattr(
        rate_limiter, "wait_for_interval", lambda seconds: wait_calls.append(seconds)
    )

    weekly_summary_service.run_retroactive_generation(seeded_session, today=dt.date(2026, 8, 24))

    assert len(wait_calls) == 2  # 生成2件分、毎回呼び出し間隔を確認している


# --- generate_for_week（匿名化版、Phase10） ---


def test_generate_for_week_anonymized_creates_separate_record(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))
    _stub_send_message(monkeypatch, response="匿名化版の本文")

    summary = weekly_summary_service.generate_for_week(
        seeded_session,
        goal,
        week_start=dt.date(2026, 8, 17),
        week_end=dt.date(2026, 8, 23),
        anonymize=True,
    )

    assert summary.is_anonymized is True
    assert summary.summary_body == "匿名化版の本文"
    assert seeded_session.query(WeeklySummary).count() == 1


def test_generate_for_week_anonymized_twice_updates_existing_record(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))
    _stub_send_message(monkeypatch, response="1回目の匿名化")

    first = weekly_summary_service.generate_for_week(
        seeded_session,
        goal,
        week_start=dt.date(2026, 8, 17),
        week_end=dt.date(2026, 8, 23),
        anonymize=True,
    )

    _stub_send_message(monkeypatch, response="2回目の匿名化")
    second = weekly_summary_service.generate_for_week(
        seeded_session,
        goal,
        week_start=dt.date(2026, 8, 17),
        week_end=dt.date(2026, 8, 23),
        anonymize=True,
    )

    assert first.id == second.id
    assert second.summary_body == "2回目の匿名化"
    assert seeded_session.query(WeeklySummary).count() == 1


# --- regenerate_all_weekly_summaries_anonymized（Phase10） ---


def test_regenerate_all_weekly_summaries_anonymized_covers_every_original_week(
    seeded_session, monkeypatch
):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 4))  # 週1
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))  # 週2
    # 「元の」（非匿名化）週次要約を用意する時点からAI呼び出しをスタブする
    # （実AI基盤への疎通に依存しないようにするため）。
    _stub_send_message(monkeypatch, response="元の週次要約")
    weekly_summary_service.generate_for_week(
        seeded_session, goal, week_start=dt.date(2026, 8, 3), week_end=dt.date(2026, 8, 9)
    )
    weekly_summary_service.generate_for_week(
        seeded_session, goal, week_start=dt.date(2026, 8, 17), week_end=dt.date(2026, 8, 23)
    )
    _stub_send_message(monkeypatch, response="匿名化済み")

    count = weekly_summary_service.regenerate_all_weekly_summaries_anonymized(seeded_session, goal)

    assert count == 2
    anonymized = (
        seeded_session.query(WeeklySummary).filter(WeeklySummary.is_anonymized.is_(True)).all()
    )
    assert len(anonymized) == 2
    assert all(row.summary_body == "匿名化済み" for row in anonymized)


def test_regenerate_all_weekly_summaries_anonymized_raises_on_failure(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))
    _stub_send_message(monkeypatch, response="元の週次要約")
    weekly_summary_service.generate_for_week(
        seeded_session, goal, week_start=dt.date(2026, 8, 17), week_end=dt.date(2026, 8, 23)
    )
    _stub_send_message(monkeypatch, raise_exc_for={"chat-0"})

    with pytest.raises(AiError):
        weekly_summary_service.regenerate_all_weekly_summaries_anonymized(seeded_session, goal)


def test_regenerate_all_weekly_summaries_anonymized_calls_on_progress_per_week(
    seeded_session, monkeypatch
):
    """1件生成するたびにon_progressが呼ばれる（Phase10注意点「進捗を表示すること」、
    export_serviceが進捗表示に用いる）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 4))
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))
    _stub_send_message(monkeypatch, response="元の週次要約")
    weekly_summary_service.generate_for_week(
        seeded_session, goal, week_start=dt.date(2026, 8, 3), week_end=dt.date(2026, 8, 9)
    )
    weekly_summary_service.generate_for_week(
        seeded_session, goal, week_start=dt.date(2026, 8, 17), week_end=dt.date(2026, 8, 23)
    )
    _stub_send_message(monkeypatch, response="匿名化済み")
    calls = []

    weekly_summary_service.regenerate_all_weekly_summaries_anonymized(
        seeded_session, goal, on_progress=lambda: calls.append(1)
    )

    assert len(calls) == 2


# --- count_pending_anonymization_weeks（Phase10） ---


def test_count_pending_anonymization_weeks_counts_non_anonymized_weeks(seeded_session, monkeypatch):
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 4))
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))
    _stub_send_message(monkeypatch, response="元の週次要約")
    weekly_summary_service.generate_for_week(
        seeded_session, goal, week_start=dt.date(2026, 8, 3), week_end=dt.date(2026, 8, 9)
    )
    weekly_summary_service.generate_for_week(
        seeded_session, goal, week_start=dt.date(2026, 8, 17), week_end=dt.date(2026, 8, 23)
    )

    assert weekly_summary_service.count_pending_anonymization_weeks(seeded_session, goal) == 2


def test_count_pending_anonymization_weeks_is_zero_without_summaries(seeded_session):
    goal = _make_goal(seeded_session)

    assert weekly_summary_service.count_pending_anonymization_weeks(seeded_session, goal) == 0
