"""weekly_summary_service のテスト（ロジック・プロンプト編15章・17.3、
実装フェーズ分割計画書Phase5完了条件「週次要約が起動時に遡及生成される」
「遡及生成時に呼び出し間隔の下限が守られる」）。
"""

import datetime as dt

import pytest
from sqlalchemy import select

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.ai.exceptions import AiError
from app.constants.app_setting_keys import SUMMARY_RETROACTIVE_MAX_PER_RUN
from app.constants.enums import GoalStatus, QualityMetricType
from app.models.ai import AiConversation, AiLog
from app.models.goal import Goal
from app.models.material import Material
from app.models.record import DailyRecord, StudyLog, WeeklySummary
from app.models.setting import AppSetting
from app.services import weekly_summary_service
from app.services.weekly_summary_service import _last_completed_sunday
from tests import reading_helpers


def _set_setting(session, key, value):
    row = session.scalar(select(AppSetting).where(AppSetting.key == key))
    row.value = value
    session.flush()


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
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert len(pending) == 1
    assert pending[0].goal.id == goal.id
    assert pending[0].week_start == dt.date(2026, 8, 17)
    assert pending[0].week_end == dt.date(2026, 8, 23)


def _make_reading_goal_with_recall(session, record_date, name="読書目標A", recall_body="想起本文"):
    """読書目標（category=READING）に、指定日の想起記録を1件作成する（L-11。
    以前はstudy_logを持たないため週次要約の対象から自動的に除外されていたが、
    読書用週次要約（17.11）の新設により対象に含まれるようになった）。
    """
    from app.constants.enums import GoalCategory, RecordState
    from app.models.record import ReadingLog

    reading_goal = Goal(
        category=GoalCategory.READING,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(reading_goal)
    session.flush()
    book = reading_helpers.make_book(session, reading_goal.id)
    record = DailyRecord(record_date=record_date, reading_record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    session.add(ReadingLog(daily_record_id=record.id, book_id=book.id, recall_body=recall_body))
    session.flush()
    return reading_goal, book


def _make_work_goal_with_log(session, record_date, name="仕事目標A", body="業務内容"):
    """仕事目標（category=WORK）に、指定日の業務記録を1件作成する（L-11。
    以前はstudy_logを持たないため週次要約の対象から自動的に除外されていたが、
    仕事用週次要約（17.12）の新設により対象に含まれるようになった）。
    """
    from app.constants.enums import GoalCategory, RecordState
    from app.models.record import WorkLog
    from app.models.work import WorkAssignment

    work_goal = Goal(
        category=GoalCategory.WORK,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    session.add(work_goal)
    session.flush()
    work_assignment = WorkAssignment(
        goal_id=work_goal.id, expected_content="想定業務内容", start_date=dt.date(2026, 1, 1)
    )
    session.add(work_assignment)
    session.flush()
    record = DailyRecord(record_date=record_date, work_record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    session.add(
        WorkLog(daily_record_id=record.id, work_assignment_id=work_assignment.id, body=body)
    )
    session.flush()
    return work_goal, work_assignment


def test_list_pending_weeks_includes_reading_goals_with_recall_logs(seeded_session):
    """読書目標（category=READING）はreading_logがあれば週次要約の生成対象に含まれる
    （L-11、17.11新設。以前はstudy_logの有無で判定していたため自動的に除外されていた）。
    """
    reading_goal, _book = _make_reading_goal_with_recall(seeded_session, dt.date(2026, 8, 18))

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert len(pending) == 1
    assert pending[0].goal.id == reading_goal.id
    assert pending[0].week_start == dt.date(2026, 8, 17)
    assert pending[0].week_end == dt.date(2026, 8, 23)


def test_list_pending_weeks_includes_work_goals_with_work_logs(seeded_session):
    """仕事目標（category=WORK）はwork_logがあれば週次要約の生成対象に含まれる
    （読書と同じ理由。L-11、17.12新設）。
    """
    work_goal, _work_assignment = _make_work_goal_with_log(seeded_session, dt.date(2026, 8, 18))

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert len(pending) == 1
    assert pending[0].goal.id == work_goal.id
    assert pending[0].week_start == dt.date(2026, 8, 17)
    assert pending[0].week_end == dt.date(2026, 8, 23)


def test_list_pending_weeks_covers_three_categories_in_the_same_week(seeded_session):
    """同じ週に資格試験・読書・仕事の3カテゴリの実績があれば、3件とも生成対象に含まれる
    （L-11、カテゴリ横断の横展開確認）。"""
    exam_goal = _make_goal(seeded_session, name="資格目標A")
    material = _make_material(seeded_session, exam_goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))
    reading_goal, _book = _make_reading_goal_with_recall(seeded_session, dt.date(2026, 8, 19))
    work_goal, _work_assignment = _make_work_goal_with_log(seeded_session, dt.date(2026, 8, 20))

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert {item.goal.id for item in pending} == {exam_goal.id, reading_goal.id, work_goal.id}


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
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert pending == []


def test_list_pending_weeks_excludes_weeks_without_logs(seeded_session):
    _make_goal(seeded_session)

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert pending == []


def test_list_pending_weeks_reaches_back_to_goal_start_date(seeded_session):
    """遡及対象は固定週数ではなく目標開始日まで広がる（G3）。旧実装では
    lookback_weeks=4の範囲外だった5週間前の実績も対象に含まれることを確認する。"""
    goal = _make_goal(seeded_session)  # start_date=2026-01-01
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 7, 21))  # 5週間前

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert len(pending) == 1
    assert pending[0].week_start == dt.date(2026, 7, 20)
    assert pending[0].week_end == dt.date(2026, 7, 26)


def test_list_pending_weeks_orders_newest_week_first(seeded_session):
    """戻り値は新しい週が先頭（G3決定事項：新しい週から生成する）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 7, 21))  # 5週間前
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))  # 直近週

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert [item.week_start for item in pending] == [dt.date(2026, 8, 17), dt.date(2026, 7, 20)]


def test_list_pending_weeks_reading_reaches_back_to_book_start_date(seeded_session):
    """読書目標の遡及基準はgoal.start_dateとは独立なbook.start_date（L-12と同じ区別、G3）。

    book.start_dateをgoal.start_dateより前にし、ログの週をその間（book.start_date以降・
    goal.start_dateより前）に置く。goal.start_dateを基準にする実装では、このログの週が
    遡及対象の範囲外（走査開始週より後ろ）になり該当週が1件も見つからなくなる
    （ミューテーションテストで確認済み。effective_start_dateをgoal.start_dateへ差し替えると
    本テストが失敗することを検証した）。
    """
    from app.constants.enums import GoalCategory, RecordState
    from app.models.record import ReadingLog

    reading_goal = Goal(
        category=GoalCategory.READING,
        name="読書目標B",
        start_date=dt.date(2026, 8, 1),
        status=GoalStatus.ACTIVE,
    )
    seeded_session.add(reading_goal)
    seeded_session.flush()
    book = reading_helpers.make_book(
        seeded_session, reading_goal.id, start_date=dt.date(2026, 7, 1)
    )
    record = DailyRecord(
        record_date=dt.date(2026, 7, 14), reading_record_state=RecordState.PROGRESS_ONLY
    )
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        ReadingLog(daily_record_id=record.id, book_id=book.id, recall_body="想起本文")
    )
    seeded_session.flush()

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert len(pending) == 1
    assert pending[0].goal.id == reading_goal.id
    assert pending[0].week_start == dt.date(2026, 7, 13)


def test_list_pending_weeks_returns_empty_when_no_goals(seeded_session):
    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert pending == []


def test_list_pending_weeks_returns_empty_when_goal_started_this_week(seeded_session):
    """目標が今週（まだ完了していない週）に開始した場合、遡及対象の完了週はまだ存在しない。"""
    goal = Goal(name="今週開始の目標", start_date=dt.date(2026, 8, 24), status=GoalStatus.ACTIVE)
    seeded_session.add(goal)
    seeded_session.flush()

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert pending == []


# --- invalidate_week（G4：修正時の再生成） ---


def test_invalidate_week_deletes_matching_non_anonymized_summary(seeded_session):
    goal = _make_goal(seeded_session)
    summary = WeeklySummary(
        goal_id=goal.id,
        week_start_date=dt.date(2026, 8, 17),
        week_end_date=dt.date(2026, 8, 23),
        summary_body="既に生成済み",
    )
    seeded_session.add(summary)
    seeded_session.flush()

    weekly_summary_service.invalidate_week(seeded_session, goal, dt.date(2026, 8, 18))
    seeded_session.flush()

    assert seeded_session.get(WeeklySummary, summary.id) is None


def test_invalidate_week_deletes_matching_anonymized_summary_too(seeded_session):
    """非匿名化版だけでなく匿名化版（is_anonymized=True）も同時に削除する（開発Todo S06 D3・D4。
    非匿名化版だけ残すと、regenerate_all_weekly_summaries_anonymizedが基準にする
    _non_anonymized_weeks_queryからこの週が外れたまま古い匿名化版だけが残ってしまう）。"""
    goal = _make_goal(seeded_session)
    non_anon = WeeklySummary(
        goal_id=goal.id,
        week_start_date=dt.date(2026, 8, 17),
        week_end_date=dt.date(2026, 8, 23),
        summary_body="非匿名化版",
        is_anonymized=False,
    )
    anon = WeeklySummary(
        goal_id=goal.id,
        week_start_date=dt.date(2026, 8, 17),
        week_end_date=dt.date(2026, 8, 23),
        summary_body="匿名化版",
        is_anonymized=True,
    )
    seeded_session.add_all([non_anon, anon])
    seeded_session.flush()

    weekly_summary_service.invalidate_week(seeded_session, goal, dt.date(2026, 8, 20))
    seeded_session.flush()

    assert seeded_session.get(WeeklySummary, non_anon.id) is None
    assert seeded_session.get(WeeklySummary, anon.id) is None


def test_invalidate_week_does_not_touch_other_weeks_or_goals(seeded_session):
    goal = _make_goal(seeded_session)
    other_goal = _make_goal(seeded_session, name="目標B")
    same_goal_other_week = WeeklySummary(
        goal_id=goal.id,
        week_start_date=dt.date(2026, 8, 24),
        week_end_date=dt.date(2026, 8, 30),
        summary_body="別の週",
    )
    other_goal_same_week = WeeklySummary(
        goal_id=other_goal.id,
        week_start_date=dt.date(2026, 8, 17),
        week_end_date=dt.date(2026, 8, 23),
        summary_body="別の目標",
    )
    seeded_session.add_all([same_goal_other_week, other_goal_same_week])
    seeded_session.flush()

    weekly_summary_service.invalidate_week(seeded_session, goal, dt.date(2026, 8, 18))
    seeded_session.flush()

    assert seeded_session.get(WeeklySummary, same_goal_other_week.id) is not None
    assert seeded_session.get(WeeklySummary, other_goal_same_week.id) is not None


def test_invalidate_week_is_noop_when_no_summary_exists(seeded_session):
    """無効化対象の週がまだ生成されていない場合（未完了週への入力時など）は何も削除せず、
    例外も起きない（開発Todo S06 D8）。"""
    goal = _make_goal(seeded_session)

    weekly_summary_service.invalidate_week(seeded_session, goal, dt.date(2026, 8, 18))

    assert seeded_session.query(WeeklySummary).count() == 0


def test_invalidate_week_makes_the_week_pending_again(seeded_session):
    """無効化後は、list_pending_weeksが再びその週を未生成として返す（削除方式が
    既存のpending判定とそのまま噛み合うことの回帰確認、開発Todo S06 D1・D2）。"""
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
    assert (
        weekly_summary_service.list_pending_weeks(seeded_session, today=dt.date(2026, 8, 24))
        == []
    )

    weekly_summary_service.invalidate_week(seeded_session, goal, dt.date(2026, 8, 18))
    seeded_session.flush()

    pending = weekly_summary_service.list_pending_weeks(
        seeded_session, today=dt.date(2026, 8, 24)
    )
    assert len(pending) == 1
    assert pending[0].goal.id == goal.id
    assert pending[0].week_start == dt.date(2026, 8, 17)


# --- invalidate_weeks（G4：複数件の一括無効化） ---


def test_invalidate_weeks_deletes_for_each_distinct_goal(seeded_session):
    goal_a = _make_goal(seeded_session, name="目標A")
    goal_b = _make_goal(seeded_session, name="目標B")
    week_start = dt.date(2026, 8, 17)
    summary_a = WeeklySummary(
        goal_id=goal_a.id,
        week_start_date=week_start,
        week_end_date=dt.date(2026, 8, 23),
        summary_body="目標Aの週次要約",
    )
    summary_b = WeeklySummary(
        goal_id=goal_b.id,
        week_start_date=week_start,
        week_end_date=dt.date(2026, 8, 23),
        summary_body="目標Bの週次要約",
    )
    seeded_session.add_all([summary_a, summary_b])
    seeded_session.flush()

    weekly_summary_service.invalidate_weeks(seeded_session, [goal_a, goal_b], dt.date(2026, 8, 18))
    seeded_session.flush()

    assert seeded_session.get(WeeklySummary, summary_a.id) is None
    assert seeded_session.get(WeeklySummary, summary_b.id) is None


def test_invalidate_weeks_skips_duplicate_goals(seeded_session):
    """同一目標が複数件渡された場合、2件目以降はDELETEを発行しない（CLAUDE.md
    パフォーマンスチェック。同一目標の教材・書籍・案件を1回の登録で複数件更新した場合に、
    同じgoal_id+week_start_dateへのDELETEが件数分発行されないことの確認）。"""
    goal = _make_goal(seeded_session)
    summary = WeeklySummary(
        goal_id=goal.id,
        week_start_date=dt.date(2026, 8, 17),
        week_end_date=dt.date(2026, 8, 23),
        summary_body="既に生成済み",
    )
    seeded_session.add(summary)
    seeded_session.flush()

    dup_goals = [goal, goal, goal]
    weekly_summary_service.invalidate_weeks(seeded_session, dup_goals, dt.date(2026, 8, 18))
    seeded_session.flush()

    assert seeded_session.get(WeeklySummary, summary.id) is None


def test_invalidate_weeks_handles_empty_goals(seeded_session):
    """対象の目標が無い場合（空リスト）は何もしない（register_progress/finalize_*が
    items=[]で呼ばれた場合に相当）。"""
    weekly_summary_service.invalidate_weeks(seeded_session, [], dt.date(2026, 8, 18))


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


def test_generate_for_week_reading_uses_reading_purpose_and_book_variables(
    seeded_session, monkeypatch
):
    """読書目標はWEEKLY_SUMMARY_READING（17.11）を使い、{{book_title}}・{{week_recalls}}が
    注入されること（L-11、goal.categoryによる分岐の確認）。"""
    from app.constants.enums import AiPurpose

    reading_goal, book = _make_reading_goal_with_recall(
        seeded_session, dt.date(2026, 8, 18), recall_body="週次要約対象の想起本文"
    )
    calls = _stub_send_message(monkeypatch, response="読書週次要約の本文")

    summary = weekly_summary_service.generate_for_week(
        seeded_session, reading_goal, week_start=dt.date(2026, 8, 17), week_end=dt.date(2026, 8, 23)
    )

    assert summary.goal_id == reading_goal.id
    assert summary.summary_body == "読書週次要約の本文"
    assert book.title in calls[0]["message"]
    assert "週次要約対象の想起本文" in calls[0]["message"]
    ai_log = seeded_session.query(AiLog).one()
    assert ai_log.purpose == AiPurpose.WEEKLY_SUMMARY_READING


def test_generate_for_week_work_uses_work_purpose_and_work_variables(seeded_session, monkeypatch):
    """仕事目標はWEEKLY_SUMMARY_WORK（17.12）を使い、{{work_name}}・{{week_logs}}が
    注入されること（L-11、goal.categoryによる分岐の確認）。"""
    from app.constants.enums import AiPurpose

    work_goal, _work_assignment = _make_work_goal_with_log(
        seeded_session, dt.date(2026, 8, 18), name="仕事目標X", body="週次要約対象の業務内容"
    )
    calls = _stub_send_message(monkeypatch, response="仕事週次要約の本文")

    summary = weekly_summary_service.generate_for_week(
        seeded_session, work_goal, week_start=dt.date(2026, 8, 17), week_end=dt.date(2026, 8, 23)
    )

    assert summary.goal_id == work_goal.id
    assert summary.summary_body == "仕事週次要約の本文"
    assert "仕事目標X" in calls[0]["message"]
    assert "週次要約対象の業務内容" in calls[0]["message"]
    ai_log = seeded_session.query(AiLog).one()
    assert ai_log.purpose == AiPurpose.WEEKLY_SUMMARY_WORK


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


def test_run_retroactive_generation_continues_after_one_failure(
    seeded_session, monkeypatch, caplog
):
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
    assert "週次要約の遡及生成に失敗しました" in caplog.text
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


def test_run_retroactive_generation_respects_max_per_run(seeded_session, monkeypatch):
    """1回の起動で生成する件数はsummary.retroactive_max_per_runで区切られる（G3）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    # 3週分の未生成週を用意し、上限を2に設定する。
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 4))  # 3週前
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 11))  # 2週前
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))  # 直近週
    seeded_session.commit()
    _set_setting(seeded_session, SUMMARY_RETROACTIVE_MAX_PER_RUN, "2")
    _stub_send_message(monkeypatch)

    generated = weekly_summary_service.run_retroactive_generation(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert generated == 2
    assert seeded_session.query(WeeklySummary).count() == 2


def test_run_retroactive_generation_generates_newest_week_first(seeded_session, monkeypatch):
    """上限に達した場合、新しい週が優先して生成される（G3決定事項）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 4))  # 3週前
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))  # 直近週
    seeded_session.commit()
    _set_setting(seeded_session, SUMMARY_RETROACTIVE_MAX_PER_RUN, "1")
    _stub_send_message(monkeypatch)

    weekly_summary_service.run_retroactive_generation(seeded_session, today=dt.date(2026, 8, 24))

    summary = seeded_session.query(WeeklySummary).one()
    assert summary.week_start_date == dt.date(2026, 8, 17)


def test_run_retroactive_generation_picks_up_remaining_weeks_on_next_run(
    seeded_session, monkeypatch
):
    """上限で見送られた古い週は、次回以降の起動呼び出しで生成される（G3）。"""
    goal = _make_goal(seeded_session)
    material = _make_material(seeded_session, goal)
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 4))  # 3週前
    _make_daily_record_with_log(seeded_session, material, dt.date(2026, 8, 18))  # 直近週
    seeded_session.commit()
    _set_setting(seeded_session, SUMMARY_RETROACTIVE_MAX_PER_RUN, "1")
    _stub_send_message(monkeypatch)

    first_run = weekly_summary_service.run_retroactive_generation(
        seeded_session, today=dt.date(2026, 8, 24)
    )
    second_run = weekly_summary_service.run_retroactive_generation(
        seeded_session, today=dt.date(2026, 8, 24)
    )

    assert first_run == 1
    assert second_run == 1
    assert {
        row.week_start_date for row in seeded_session.query(WeeklySummary).all()
    } == {dt.date(2026, 8, 17), dt.date(2026, 8, 3)}


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
