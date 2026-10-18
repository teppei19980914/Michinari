"""ai_context_work のテスト（仕事目標、ロジック・プロンプト編17.4・17.8〜17.10・17.12、
要件定義書6.11、実装フェーズ分割計画書Phase22・S01）。共通処理のテストは
`test_ai_context_common.py`を参照。

どのAIプロンプトへ渡す文言もPhase2〜4の既存算出ロジックの組み合わせであるため、
ここでは「必要な情報が文言に含まれているか」を中心に検証し、算出式自体の正しさは
各サービスの既存テスト（test_speed_service.py等）に委ねる（DRYの原則）。
"""

import datetime as dt

from app.constants.enums import (
    GoalCategory,
    GoalStatus,
    RecordState,
    RetrospectivePeriodType,
    WorkMemberGender,
)
from app.models.goal import Goal
from app.models.record import DailyRecord, WorkLog
from app.models.retrospective import GoalRetrospective
from app.models.work import WorkAssignment, WorkMember
from app.services import ai_context_work, settings_service
from app.services.record_service_work import WorkLogItem
from tests import ai_context_helpers


def _make_goal(session, name="目標A"):
    return ai_context_helpers.make_goal(session, name=name)


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


def _make_work_assignment(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id,
        expected_content="想定業務内容",
        start_date=dt.date(2026, 1, 1),
    )
    defaults.update(overrides)
    work_assignment = WorkAssignment(**defaults)
    session.add(work_assignment)
    session.flush()
    return work_assignment


def _add_work_log(session, work_assignment_id, record_date, **overrides):
    record = DailyRecord(record_date=record_date, work_record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    defaults = dict(
        daily_record_id=record.id, work_assignment_id=work_assignment_id, body="業務内容本文"
    )
    defaults.update(overrides)
    session.add(WorkLog(**defaults))
    session.flush()


def _make_work_member(session, work_assignment, **overrides):
    defaults = dict(work_assignment_id=work_assignment.id, name="Aさん")
    defaults.update(overrides)
    member = WorkMember(**defaults)
    session.add(member)
    session.flush()
    return member


# --- list_active_work_goals / list_active_work_assignments ---


def test_list_active_work_goals_excludes_exam_goals(seeded_session):
    exam_goal = _make_goal(seeded_session, name="資格目標")
    work_goal = _make_work_goal(seeded_session)

    active = ai_context_work.list_active_work_goals(seeded_session)

    assert work_goal.id in {g.id for g in active}
    assert exam_goal.id not in {g.id for g in active}


def test_list_active_work_assignments_returns_assignment_of_each_goal(seeded_session):
    goal_with_assignment = _make_work_goal(seeded_session, name="仕事目標A")
    work_assignment = _make_work_assignment(seeded_session, goal_with_assignment)
    goal_without_assignment = _make_work_goal(seeded_session, name="仕事目標B")

    assignments = ai_context_work.list_active_work_assignments(
        [goal_with_assignment, goal_without_assignment]
    )

    assert assignments == [work_assignment]


# --- build_daily_work_summary_text / build_today_work_text ---


def test_build_daily_work_summary_text_includes_name_and_elapsed_days(seeded_session):
    goal = _make_work_goal(seeded_session, name="仕事目標X")
    work_assignment = _make_work_assignment(
        seeded_session, goal, client_name="A社", start_date=dt.date(2026, 1, 1)
    )

    text = ai_context_work.build_daily_work_summary_text([work_assignment], dt.date(2026, 1, 11))

    assert "仕事目標X" in text
    assert "A社" in text
    assert "経過日数: 10日" in text


def test_build_daily_work_summary_text_handles_no_assignments():
    text = ai_context_work.build_daily_work_summary_text([], dt.date(2026, 1, 10))
    assert "進行中の仕事目標はありません" in text


def test_build_today_work_text_includes_goal_name_and_body(seeded_session):
    goal = _make_work_goal(seeded_session, name="仕事目標X")
    work_assignment = _make_work_assignment(seeded_session, goal)
    item = WorkLogItem(work_assignment_id=work_assignment.id, body="今日はAPIを実装した")

    text = ai_context_work.build_today_work_text([item], {work_assignment.id: work_assignment})

    assert "仕事目標X" in text
    assert "今日はAPIを実装した" in text


def test_build_today_work_text_handles_no_items():
    text = ai_context_work.build_today_work_text([], {})
    assert "本日の業務記録はまだありません" in text


# --- build_recent_work_logs_entries（S04 G1：period_start/period_endの全期間指定） ---


def test_build_recent_work_logs_entries_excludes_entries_outside_period(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 9), body="期間内の記録")
    _add_work_log(seeded_session, work_assignment.id, dt.date(2025, 12, 1), body="期間外の記録")

    entries = ai_context_work.build_recent_work_logs_entries(
        seeded_session,
        [work_assignment],
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 1, 9),
    )

    texts = [entry.text for entry in entries]
    assert any("期間内の記録" in text for text in texts)
    assert not any("期間外の記録" in text for text in texts)


def test_build_recent_work_logs_entries_excludes_todays_own_record(seeded_session):
    """対象日（today）自身の業務記録は含めない。理由はbuild_recent_recalls_entriesと同じ
    （2026-09-15是正）。呼び出し側がperiod_end=today-1を渡すことでtodayを除外する（S04）。"""
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 10), body="本日分の記録")
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 9), body="前日分の記録")

    entries = ai_context_work.build_recent_work_logs_entries(
        seeded_session,
        [work_assignment],
        period_start=dt.date(2025, 1, 1),
        period_end=dt.date(2026, 1, 9),
    )

    texts = [entry.text for entry in entries]
    assert not any("本日分の記録" in text for text in texts)
    assert any("前日分の記録" in text for text in texts)


def test_build_recent_work_logs_entries_orders_oldest_first(seeded_session):
    # build_with_degradable_entriesの段階（古い日から除外）はリスト先頭を古い順と
    # 前提しているため、record_dateの昇順で返ることを固定する（16.5・22.4）。
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 9), body="新しい記録")
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 8), body="古い記録")

    entries = ai_context_work.build_recent_work_logs_entries(
        seeded_session,
        [work_assignment],
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 1, 9),
    )

    assert [entry.record_date for entry in entries] == [dt.date(2026, 1, 8), dt.date(2026, 1, 9)]


def test_build_recent_work_logs_entries_handles_no_assignments(seeded_session):
    entries = ai_context_work.build_recent_work_logs_entries(
        seeded_session, [], period_start=dt.date(2026, 1, 1), period_end=dt.date(2026, 1, 9)
    )
    assert entries == []


def test_build_recent_work_logs_entries_handles_no_logs(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)

    entries = ai_context_work.build_recent_work_logs_entries(
        seeded_session,
        [work_assignment],
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 1, 9),
    )

    assert entries == []


# --- build_retrospective_work_summary_text / build_work_logs_entries_for_period ---


def test_build_retrospective_work_summary_text_includes_client_and_start_date(seeded_session):
    goal = _make_work_goal(seeded_session, name="仕事目標X")
    work_assignment = _make_work_assignment(
        seeded_session,
        goal,
        client_name="B社",
        expected_content="Webサイト改修",
        start_date=dt.date(2026, 2, 1),
    )

    text = ai_context_work.build_retrospective_work_summary_text(work_assignment)

    assert "仕事目標X" in text
    assert "B社" in text
    assert "Webサイト改修" in text
    assert "2026-02-01" in text


def test_build_work_logs_entries_for_period_orders_chronologically(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 2), body="2日目の業務")
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 1), body="1日目の業務")

    entries = ai_context_work.build_work_logs_entries_for_period(
        seeded_session, work_assignment, dt.date(2026, 1, 1), dt.date(2026, 1, 31)
    )

    assert [entry.record_date for entry in entries] == [dt.date(2026, 1, 1), dt.date(2026, 1, 2)]


def test_build_work_logs_entries_for_period_excludes_entries_outside_range(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 15), body="範囲内の業務")
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 2, 1), body="範囲外の業務")

    entries = ai_context_work.build_work_logs_entries_for_period(
        seeded_session, work_assignment, dt.date(2026, 1, 1), dt.date(2026, 1, 31)
    )

    texts = [entry.text for entry in entries]
    assert any("範囲内の業務" in text for text in texts)
    assert not any("範囲外の業務" in text for text in texts)


def test_build_work_logs_entries_for_period_handles_no_logs(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)

    entries = ai_context_work.build_work_logs_entries_for_period(
        seeded_session, work_assignment, dt.date(2026, 1, 1), dt.date(2026, 1, 31)
    )

    assert entries == []


# --- build_week_work_logs_text ---


def test_build_week_work_logs_text_lists_entries_within_range(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 9), body="窓内の記録")
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 20), body="窓外の記録")

    text = ai_context_work.build_week_work_logs_text(
        seeded_session, work_assignment, dt.date(2026, 1, 5), dt.date(2026, 1, 11)
    )

    assert "窓内の記録" in text
    assert "窓外の記録" not in text


def test_build_week_work_logs_text_handles_no_logs(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)

    text = ai_context_work.build_week_work_logs_text(
        seeded_session, work_assignment, dt.date(2026, 1, 5), dt.date(2026, 1, 11)
    )

    assert "この週の業務記録はありません" in text


# --- build_work_progress_summary / build_work_recent_activity_text ---


def test_build_work_progress_summary_includes_elapsed_days_and_streak(seeded_session):
    goal = _make_work_goal(seeded_session, name="仕事目標X")
    work_assignment = _make_work_assignment(seeded_session, goal, start_date=dt.date(2026, 1, 1))
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 1, 10))

    text = ai_context_work.build_work_progress_summary(
        seeded_session, [work_assignment], dt.date(2026, 1, 10)
    )

    assert "仕事目標X" in text
    assert "経過9日" in text
    assert "連続記録1日" in text
    assert "直近記録日 2026-01-10" in text
    assert "直近の月次報告なし" in text


def test_build_work_progress_summary_includes_recent_monthly_report(seeded_session):
    """22.1: WORK用の{{progress_summary}}は直近の月次報告有無を含める
    （未生成の期に「今日の一言」から月次報告の作成を促せるようにするため）。"""
    goal = _make_work_goal(seeded_session, name="仕事目標Y")
    work_assignment = _make_work_assignment(seeded_session, goal, start_date=dt.date(2026, 1, 1))
    seeded_session.add(
        GoalRetrospective(
            goal_id=goal.id,
            body="前月の月次報告",
            period_type=RetrospectivePeriodType.MONTHLY,
            period_key="2026-01",
        )
    )
    seeded_session.flush()

    text = ai_context_work.build_work_progress_summary(
        seeded_session, [work_assignment], dt.date(2026, 2, 10)
    )

    assert "直近の月次報告あり" in text


def test_build_work_progress_summary_handles_no_assignments(seeded_session):
    text = ai_context_work.build_work_progress_summary(seeded_session, [], dt.date(2026, 1, 10))
    assert "対象案件はありません" in text


def test_build_work_recent_activity_text_counts_reported_days(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    record = DailyRecord(record_date=dt.date(2026, 1, 9), work_record_state=RecordState.REPORTED)
    seeded_session.add(record)
    seeded_session.flush()
    seeded_session.add(
        WorkLog(daily_record_id=record.id, work_assignment_id=work_assignment.id, body="業務内容")
    )
    seeded_session.flush()

    text = ai_context_work.build_work_recent_activity_text(
        seeded_session, [work_assignment], dt.date(2026, 1, 10)
    )

    assert "記録日数: 1日" in text
    assert "報告確定 1日" in text


def test_build_work_recent_activity_text_handles_no_assignments(seeded_session):
    text = ai_context_work.build_work_recent_activity_text(seeded_session, [], dt.date(2026, 1, 10))
    assert "対象案件はありません" in text


def test_build_work_recent_activity_text_handles_no_logs(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)

    text = ai_context_work.build_work_recent_activity_text(
        seeded_session, [work_assignment], dt.date(2026, 1, 10)
    )

    assert "直近の業務記録はありません" in text


# --- build_evaluation_member_summary_text ---


def test_build_evaluation_member_summary_text_includes_gender_and_characteristics(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    member = _make_work_member(
        seeded_session,
        work_assignment,
        gender=WorkMemberGender.FEMALE,
        characteristics="粘り強い性格",
    )

    text = ai_context_work.build_evaluation_member_summary_text(seeded_session, member)

    assert "氏名: Aさん" in text
    assert "性別: 女性" in text
    assert "特徴・性格: 粘り強い性格" in text


def test_build_evaluation_member_summary_text_omits_unset_fields(seeded_session):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    member = _make_work_member(seeded_session, work_assignment)

    text = ai_context_work.build_evaluation_member_summary_text(seeded_session, member)

    assert text == "氏名: Aさん"


def test_build_evaluation_member_summary_text_uses_english_gender_label_when_locale_is_english(
    seeded_session,
):
    settings_service.update_app_settings(seeded_session, display={"locale": "en"})
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    member = _make_work_member(seeded_session, work_assignment, gender=WorkMemberGender.FEMALE)

    text = ai_context_work.build_evaluation_member_summary_text(seeded_session, member)

    assert "性別: female" in text
    assert "女性" not in text
