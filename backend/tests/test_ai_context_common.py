"""ai_context_common のテスト（ロジック・プロンプト編17.2〜17.4、実装フェーズ分割計画書Phase5・
S01）。資格試験・読書・仕事の2カテゴリ以上から参照される共通処理のみを対象とする。
カテゴリ固有の処理のテストは`test_ai_context_exam.py`・`test_ai_context_reading.py`・
`test_ai_context_work.py`を参照。

どのAIプロンプトへ渡す文言もPhase2〜4の既存算出ロジックの組み合わせであるため、
ここでは「必要な情報が文言に含まれているか」を中心に検証し、算出式自体の正しさは
各サービスの既存テスト（test_speed_service.py等）に委ねる（DRYの原則）。
"""

import datetime as dt

import pytest

from app.constants.enums import GoalCategory, GoalStatus
from app.models.goal import Goal
from app.models.record import WeeklySummary
from app.services import ai_context_common
from tests import ai_context_helpers


def _make_goal(session, name="目標A", status=GoalStatus.ACTIVE):
    return ai_context_helpers.make_goal(session, name=name, status=status)


# --- list_active_goals ---


def test_list_active_goals_excludes_non_active(seeded_session):
    active = _make_goal(seeded_session, name="進行中", status=GoalStatus.ACTIVE)
    _make_goal(seeded_session, name="下書き", status=GoalStatus.DRAFT)

    result = ai_context_common.list_active_goals(seeded_session)

    assert [g.id for g in result] == [active.id]


# --- resolve_weekly_compressed_period／exclude_covered_dates（L-11、2026-09-16是正） ---


def _add_weekly_summary(session, goal, week_start, *, summary_body=None, is_anonymized=False):
    week_end = week_start + dt.timedelta(days=6)
    session.add(
        WeeklySummary(
            goal_id=goal.id,
            week_start_date=week_start,
            week_end_date=week_end,
            summary_body=summary_body or f"{week_start.isoformat()}の要約",
            is_anonymized=is_anonymized,
        )
    )
    session.flush()
    return week_end


def test_resolve_weekly_compressed_period_no_summaries_returns_empty(seeded_session):
    goal = _make_goal(seeded_session)

    result = ai_context_common.resolve_weekly_compressed_period(
        seeded_session, goal, period_start=dt.date(2026, 7, 6), period_end=dt.date(2026, 7, 26)
    )

    assert result.weekly_summary_entries == []
    assert result.covered_ranges == []


def test_resolve_weekly_compressed_period_includes_all_weeks_fully_inside_period(seeded_session):
    """period_startが週境界（月曜）と一致しなくても、[period_start, period_end]に
    フル収容される週次要約はすべて圧縮対象とする（2026-09-16是正。旧実装はperiod_startと
    週開始日が完全一致する場合しか圧縮が発動しないバグがあった）。"""
    goal = _make_goal(seeded_session)
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 6))  # 7/6-7/12
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 13))  # 7/13-7/19

    # period_startを週開始日からわざと1日ずらす（火曜始まり）。
    result = ai_context_common.resolve_weekly_compressed_period(
        seeded_session, goal, period_start=dt.date(2026, 7, 1), period_end=dt.date(2026, 7, 26)
    )

    assert [entry.record_date for entry in result.weekly_summary_entries] == [
        dt.date(2026, 7, 6),
        dt.date(2026, 7, 13),
    ]
    assert result.covered_ranges == [
        (dt.date(2026, 7, 6), dt.date(2026, 7, 12)),
        (dt.date(2026, 7, 13), dt.date(2026, 7, 19)),
    ]


def test_resolve_weekly_compressed_period_includes_weeks_independently_across_a_gap(
    seeded_session,
):
    """途中に未生成の週（欠け）があっても、それより後ろの週次要約は独立して圧縮対象に
    含める（旧実装は欠けで以降すべて打ち切っていたが、生ログ側はexclude_covered_datesで
    日付単位に除外するため、打ち切る必要がない、2026-09-16是正）。"""
    goal = _make_goal(seeded_session)
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 6))  # 7/6-7/12
    # 7/13週は未生成（欠け）
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 20))  # 7/20-7/26

    result = ai_context_common.resolve_weekly_compressed_period(
        seeded_session, goal, period_start=dt.date(2026, 7, 6), period_end=dt.date(2026, 8, 2)
    )

    assert [entry.record_date for entry in result.weekly_summary_entries] == [
        dt.date(2026, 7, 6),
        dt.date(2026, 7, 20),
    ]
    assert result.covered_ranges == [
        (dt.date(2026, 7, 6), dt.date(2026, 7, 12)),
        (dt.date(2026, 7, 20), dt.date(2026, 7, 26)),
    ]


def test_resolve_weekly_compressed_period_excludes_weeks_not_fully_inside_period(seeded_session):
    """開始日がperiod_startより前、または終了日がperiod_endより後ろの週は、部分的にしか
    重ならないため圧縮対象から除外する（フル収容のみ対象、L-11）。"""
    goal = _make_goal(seeded_session)
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 6, 22))  # 6/22-6/28、period_startより前
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 27))  # 7/27-8/2、period_endより後

    result = ai_context_common.resolve_weekly_compressed_period(
        seeded_session, goal, period_start=dt.date(2026, 7, 6), period_end=dt.date(2026, 7, 26)
    )

    assert result.weekly_summary_entries == []
    assert result.covered_ranges == []


def test_resolve_weekly_compressed_period_excludes_anonymized(seeded_session):
    goal = _make_goal(seeded_session)
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 6), is_anonymized=True)

    result = ai_context_common.resolve_weekly_compressed_period(
        seeded_session, goal, period_start=dt.date(2026, 7, 6), period_end=dt.date(2026, 7, 26)
    )

    assert result.weekly_summary_entries == []
    assert result.covered_ranges == []


def test_resolve_weekly_compressed_period_limit_keeps_most_recent_weeks_and_drops_oldest(
    seeded_session,
):
    """limit指定時は、period_end側に近い（新しい）方からlimit件までに絞り、古い方から
    溢れた分は圧縮対象から除外する（縮退の方向性＝直近の記憶を優先し遠い過去から
    削る、と同じ考え方をweekly_summariesの選定にも適用する、2026-09-16）。"""
    goal = _make_goal(seeded_session)
    for week_start in (dt.date(2026, 7, 6), dt.date(2026, 7, 13), dt.date(2026, 7, 20)):
        _add_weekly_summary(seeded_session, goal, week_start)

    result = ai_context_common.resolve_weekly_compressed_period(
        seeded_session,
        goal,
        period_start=dt.date(2026, 7, 6),
        period_end=dt.date(2026, 7, 26),
        limit=2,
    )

    # 新しい順に2件（7/13・7/20）を採用したのち、古い順へ並べ替える。7/6は溢れて除外。
    assert [entry.record_date for entry in result.weekly_summary_entries] == [
        dt.date(2026, 7, 13),
        dt.date(2026, 7, 20),
    ]
    assert result.covered_ranges == [
        (dt.date(2026, 7, 13), dt.date(2026, 7, 19)),
        (dt.date(2026, 7, 20), dt.date(2026, 7, 26)),
    ]


def test_exclude_covered_dates_removes_entries_within_ranges(seeded_session):
    entries = [
        ai_context_common.DatedLogEntry(record_date=dt.date(2026, 7, 6), text="7/6"),
        ai_context_common.DatedLogEntry(record_date=dt.date(2026, 7, 10), text="7/10"),
        ai_context_common.DatedLogEntry(record_date=dt.date(2026, 7, 15), text="7/15"),
    ]

    result = ai_context_common.exclude_covered_dates(
        entries, covered_ranges=[(dt.date(2026, 7, 6), dt.date(2026, 7, 12))]
    )

    assert [entry.record_date for entry in result] == [dt.date(2026, 7, 15)]


def test_exclude_covered_dates_returns_entries_unchanged_when_no_ranges(seeded_session):
    entries = [ai_context_common.DatedLogEntry(record_date=dt.date(2026, 7, 6), text="7/6")]

    result = ai_context_common.exclude_covered_dates(entries, covered_ranges=[])

    assert result == entries


# --- build_past_record_entries（S04、G1・G2共通化） ---


def test_build_past_record_entries_excludes_raw_entries_covered_by_summary(seeded_session):
    goal = _make_goal(seeded_session)
    _add_weekly_summary(seeded_session, goal, dt.date(2026, 7, 6))  # 7/6-7/12

    raw_entries = [
        ai_context_common.DatedLogEntry(record_date=dt.date(2026, 7, 8), text="7/8の生ログ"),
        ai_context_common.DatedLogEntry(record_date=dt.date(2026, 7, 15), text="7/15の生ログ"),
    ]

    result = ai_context_common.build_past_record_entries(
        seeded_session,
        goal,
        period_start=dt.date(2026, 7, 6),
        period_end=dt.date(2026, 7, 19),
        raw_entries=raw_entries,
    )

    assert [entry.record_date for entry in result.weekly_summary_entries] == [
        dt.date(2026, 7, 6)
    ]
    assert [entry.record_date for entry in result.raw_entries] == [dt.date(2026, 7, 15)]


def test_build_past_record_entries_has_no_limit_on_weekly_summary_count(seeded_session):
    """S04 G1：件数・週数の上限を設けない（limit=None）。多数の週次要約が全て圧縮対象に
    含まれることを確認する。"""
    goal = _make_goal(seeded_session)
    week_starts = [dt.date(2026, 1, 5) + dt.timedelta(days=7 * i) for i in range(10)]
    for week_start in week_starts:
        _add_weekly_summary(seeded_session, goal, week_start)

    result = ai_context_common.build_past_record_entries(
        seeded_session,
        goal,
        period_start=week_starts[0],
        period_end=week_starts[-1] + dt.timedelta(days=6),
        raw_entries=[],
    )

    assert len(result.weekly_summary_entries) == 10
    assert [entry.record_date for entry in result.weekly_summary_entries] == week_starts


def test_build_past_record_entries_returns_all_raw_entries_when_no_summary(seeded_session):
    goal = _make_goal(seeded_session)
    raw_entries = [
        ai_context_common.DatedLogEntry(record_date=dt.date(2026, 7, 6), text="7/6の生ログ"),
    ]

    result = ai_context_common.build_past_record_entries(
        seeded_session,
        goal,
        period_start=dt.date(2026, 7, 6),
        period_end=dt.date(2026, 7, 19),
        raw_entries=raw_entries,
    )

    assert result.weekly_summary_entries == []
    assert result.raw_entries == raw_entries


# --- build_anonymize_instruction ---


def test_build_anonymize_instruction_empty_when_not_anonymizing():
    assert ai_context_common.build_anonymize_instruction(False) == ""


def test_build_anonymize_instruction_returns_text_when_anonymizing():
    text = ai_context_common.build_anonymize_instruction(True)

    assert "匿名化" in text


# --- build_perspective_suggestion_instruction ---


@pytest.mark.parametrize("category", [GoalCategory.EXAM, GoalCategory.READING, GoalCategory.WORK])
def test_build_perspective_suggestion_instruction_empty_when_above_threshold(category):
    assert ai_context_common.build_perspective_suggestion_instruction(category, False) == ""


@pytest.mark.parametrize("category", [GoalCategory.EXAM, GoalCategory.READING, GoalCategory.WORK])
def test_build_perspective_suggestion_instruction_returns_category_specific_text(category):
    text = ai_context_common.build_perspective_suggestion_instruction(category, True)

    assert text != ""
    assert "断定" in text


# --- list_daily_message_target_goals ---


def test_list_daily_message_target_goals_includes_exam_and_work_excludes_reading(seeded_session):
    exam_goal = _make_goal(seeded_session, name="資格目標")
    work_goal = Goal(
        category=GoalCategory.WORK,
        name="仕事目標",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    reading_goal = Goal(
        category=GoalCategory.READING,
        name="読書目標",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    seeded_session.add_all([work_goal, reading_goal])
    seeded_session.commit()

    targets = ai_context_common.list_daily_message_target_goals(seeded_session)

    target_ids = {g.id for g in targets}
    assert exam_goal.id in target_ids
    assert work_goal.id in target_ids
    assert reading_goal.id not in target_ids
