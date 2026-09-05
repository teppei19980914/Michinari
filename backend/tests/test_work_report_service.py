"""work_report_service のテスト（設計書ロジック・プロンプト編17.9〜17.10・22.5〜22.6、
データ構造編5.4、実装フェーズ分割計画書Phase22）。

期間判定・AI応答のパース・本文組み立てはAI呼び出しを伴わない純粋なロジックのため、
ここで直接検証する（daily_feedback_service等と同じ方針、CLAUDE.md DRYの原則）。
generate_monthly_report／generate_semiannual_reviewはAI呼び出しを伴うため、
app.ai.client.send_messageをモックして検証する。
"""

import datetime as dt

import pytest

from app.ai import client as ai_client
from app.ai import rate_limiter
from app.constants.enums import GoalCategory, GoalStatus, RecordState, RetrospectivePeriodType
from app.models.goal import Goal
from app.models.record import DailyRecord, WorkLog
from app.models.retrospective import GoalRetrospective
from app.models.work import WorkAssignment
from app.services import work_report_service
from app.services.exceptions import ValidationError


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep(monkeypatch):
    monkeypatch.setattr(rate_limiter, "wait_for_interval", lambda *args, **kwargs: None)


@pytest.fixture(autouse=True)
def _cleanup_committed_rows(seeded_session):
    yield
    from app.models.base import Base

    seeded_session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        seeded_session.execute(table.delete())
    seeded_session.commit()


def _make_work_goal(session, name="仕事目標A"):
    goal = Goal(
        category=GoalCategory.WORK,
        name=name,
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
        resource_ratio=0,
    )
    session.add(goal)
    session.flush()
    return goal


def _make_work_assignment(session, goal, **overrides):
    defaults = dict(
        goal_id=goal.id, expected_content="想定業務内容", start_date=dt.date(2026, 1, 1)
    )
    defaults.update(overrides)
    work_assignment = WorkAssignment(**defaults)
    session.add(work_assignment)
    session.flush()
    return work_assignment


def _add_work_log(session, work_assignment_id, record_date, body="業務内容"):
    record = DailyRecord(record_date=record_date, record_state=RecordState.PROGRESS_ONLY)
    session.add(record)
    session.flush()
    session.add(
        WorkLog(daily_record_id=record.id, work_assignment_id=work_assignment_id, body=body)
    )
    session.flush()


def _stub_send_message(monkeypatch, *, response):
    monkeypatch.setattr(
        ai_client,
        "send_message",
        lambda session, *, chat_uid, message: ai_client.SendResult(
            response_text=response, latency_ms=5
        ),
    )
    counter = iter(range(1000))
    monkeypatch.setattr(
        ai_client,
        "create_chat_in_folder_by_name",
        lambda session, *, assistant_uid, folder_name, title: f"chat-{next(counter)}",
    )


_MONTHLY_RESPONSE = """## 業務内容の要約
今月はAPI開発を中心に取り組んだ。

## 達成度
3

## 達成状況の振り返り
テストケースを50件作成し、目標に近い水準で進捗した。

## 来月の目標
テストケースを80件作成する。

## 報告・連絡事項
特になし
"""

_SEMIANNUAL_RESPONSE = """## 業務内容の要約
半期を通じてAPI開発を継続した。

## 達成度
2

## 達成状況の振り返り
当初計画を上回るペースで進んだ。

## 次半期の目標
新機能の設計を開始する。
"""


# --- 期間判定（22.5） ---


def test_default_monthly_period_key_is_previous_month():
    assert work_report_service.default_monthly_period_key(dt.date(2026, 9, 5)) == "2026-08"


def test_default_monthly_period_key_handles_january():
    assert work_report_service.default_monthly_period_key(dt.date(2026, 1, 15)) == "2025-12"


def test_previous_monthly_period_key():
    assert work_report_service._previous_monthly_period_key("2026-01") == "2025-12"
    assert work_report_service._previous_monthly_period_key("2026-09") == "2026-08"


def test_monthly_period_range_covers_full_month():
    date_from, date_to = work_report_service._monthly_period_range("2026-02")
    assert date_from == dt.date(2026, 2, 1)
    assert date_to == dt.date(2026, 2, 28)


@pytest.mark.parametrize(
    "today, expected",
    [
        (dt.date(2026, 3, 1), "2026-H1"),
        (dt.date(2026, 8, 31), "2026-H1"),
        (dt.date(2026, 9, 1), "2026-H2"),
        (dt.date(2026, 12, 31), "2026-H2"),
        (dt.date(2027, 1, 1), "2026-H2"),
        (dt.date(2027, 2, 28), "2026-H2"),
    ],
)
def test_default_semiannual_period_key(today, expected):
    assert work_report_service.default_semiannual_period_key(today) == expected


def test_previous_semiannual_period_key():
    assert work_report_service._previous_semiannual_period_key("2026-H1") == "2025-H2"
    assert work_report_service._previous_semiannual_period_key("2026-H2") == "2026-H1"


def test_semiannual_period_range_h1():
    date_from, date_to = work_report_service._semiannual_period_range("2026-H1")
    assert date_from == dt.date(2026, 3, 1)
    assert date_to == dt.date(2026, 8, 31)


def test_semiannual_period_range_h2_leap_year():
    """H2は翌年2月末日まで。2028年は閏年のため2月29日までとなる。"""
    date_from, date_to = work_report_service._semiannual_period_range("2027-H2")
    assert date_from == dt.date(2027, 9, 1)
    assert date_to == dt.date(2028, 2, 29)


def test_semiannual_period_range_h2_non_leap_year():
    date_from, date_to = work_report_service._semiannual_period_range("2026-H2")
    assert date_from == dt.date(2026, 9, 1)
    assert date_to == dt.date(2027, 2, 28)


def test_semiannual_period_display_h2():
    assert work_report_service._semiannual_period_display("2026-H2") == "2026年9月〜2027年2月"


# --- AI応答のパース（22.6） ---


def test_parse_sections_extracts_all_headings():
    sections = work_report_service._parse_sections(
        _MONTHLY_RESPONSE, work_report_service._MONTHLY_HEADINGS
    )
    assert sections["## 業務内容の要約"] == "今月はAPI開発を中心に取り組んだ。"
    assert sections["## 達成度"] == "3"
    assert sections["## 来月の目標"] == "テストケースを80件作成する。"
    assert sections["## 報告・連絡事項"] == "特になし"


def test_parse_sections_missing_heading_returns_empty_string():
    sections = work_report_service._parse_sections(
        "見出しの無い応答", work_report_service._MONTHLY_HEADINGS
    )
    assert all(value == "" for value in sections.values())


@pytest.mark.parametrize(
    "text, expected",
    [("3", 3), ("1", 1), ("5", 5), ("対象外", None), ("6", None), ("3点", None), ("", None)],
)
def test_parse_achievement_score(text, expected):
    assert work_report_service._parse_achievement_score(text) == expected


# --- 生成（POST、既存行があれば上書き） ---


def test_generate_monthly_report_without_work_assignment_is_rejected(seeded_session):
    goal = _make_work_goal(seeded_session)
    with pytest.raises(ValidationError):
        work_report_service.generate_monthly_report(
            seeded_session, goal, period_key="2026-08", today=dt.date(2026, 9, 5)
        )


def test_generate_monthly_report_parses_sections_into_columns(seeded_session, monkeypatch):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 8, 5))
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)

    retrospective = work_report_service.generate_monthly_report(
        seeded_session, goal, period_key="2026-08", today=dt.date(2026, 9, 5)
    )

    assert retrospective.period_type == RetrospectivePeriodType.MONTHLY
    assert retrospective.period_key == "2026-08"
    assert retrospective.achievement_score == 3
    assert retrospective.next_goal_text == "テストケースを80件作成する。"
    assert retrospective.report_notes == "特になし"
    assert retrospective.edited_at is None
    assert "# 月次報告（2026年8月）" in retrospective.body
    assert "## 目標がどの程度達成されたか\n3" in retrospective.body


def test_generate_monthly_report_defaults_period_to_previous_month(seeded_session, monkeypatch):
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)

    retrospective = work_report_service.generate_monthly_report(
        seeded_session, goal, period_key=None, today=dt.date(2026, 9, 5)
    )

    assert retrospective.period_key == "2026-08"


def test_generate_monthly_report_first_time_has_no_target_goal(seeded_session, monkeypatch):
    """前月の記録が無い初回は、比較対象となる目標が無い旨を注入する（要件定義書R-83）。"""
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)

    retrospective = work_report_service.generate_monthly_report(
        seeded_session, goal, period_key="2026-08", today=dt.date(2026, 9, 5)
    )

    assert (
        retrospective.target_goal_text == "（前月の記録が無いため、今回は目標との比較を行いません）"
    )


def test_generate_monthly_report_carries_forward_previous_next_goal_text(
    seeded_session, monkeypatch
):
    """前月のnext_goal_textが今月のtarget_goal_textとして複製される（AIは関与しない）。"""
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)
    work_report_service.generate_monthly_report(
        seeded_session, goal, period_key="2026-07", today=dt.date(2026, 8, 5)
    )

    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)
    retrospective = work_report_service.generate_monthly_report(
        seeded_session, goal, period_key="2026-08", today=dt.date(2026, 9, 5)
    )

    assert retrospective.target_goal_text == "テストケースを80件作成する。"


def test_regenerate_monthly_report_overwrites_same_row(seeded_session, monkeypatch):
    """WORKの行は1期間1行（EXAM/READINGの複数行再生成方式とは異なる）。"""
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)
    first = work_report_service.generate_monthly_report(
        seeded_session, goal, period_key="2026-08", today=dt.date(2026, 9, 5)
    )

    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE.replace("3\n", "1\n"))
    second = work_report_service.generate_monthly_report(
        seeded_session, goal, period_key="2026-08", today=dt.date(2026, 9, 5)
    )

    assert first.id == second.id
    assert second.achievement_score == 1
    count = (
        seeded_session.query(GoalRetrospective)
        .filter_by(
            goal_id=goal.id, period_type=RetrospectivePeriodType.MONTHLY, period_key="2026-08"
        )
        .count()
    )
    assert count == 1


def test_generate_semiannual_review_parses_sections_into_columns(seeded_session, monkeypatch):
    goal = _make_work_goal(seeded_session)
    work_assignment = _make_work_assignment(seeded_session, goal)
    _add_work_log(seeded_session, work_assignment.id, dt.date(2026, 4, 1))
    _stub_send_message(monkeypatch, response=_SEMIANNUAL_RESPONSE)

    retrospective = work_report_service.generate_semiannual_review(
        seeded_session, goal, period_key="2026-H1", today=dt.date(2026, 8, 20)
    )

    assert retrospective.period_type == RetrospectivePeriodType.SEMI_ANNUAL
    assert retrospective.achievement_score == 2
    assert retrospective.next_goal_text == "新機能の設計を開始する。"
    assert retrospective.report_notes is None
    assert "# 半期評価（2026年3月〜8月）" in retrospective.body


def test_regenerate_semiannual_review_overwrites_same_row(seeded_session, monkeypatch):
    """WORKの行は1期間1行（monthly報告と同じ設計）。"""
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch, response=_SEMIANNUAL_RESPONSE)
    first = work_report_service.generate_semiannual_review(
        seeded_session, goal, period_key="2026-H1", today=dt.date(2026, 8, 20)
    )

    _stub_send_message(monkeypatch, response=_SEMIANNUAL_RESPONSE.replace("2\n", "4\n"))
    second = work_report_service.generate_semiannual_review(
        seeded_session, goal, period_key="2026-H1", today=dt.date(2026, 8, 20)
    )

    assert first.id == second.id
    assert second.achievement_score == 4
    count = (
        seeded_session.query(GoalRetrospective)
        .filter_by(
            goal_id=goal.id, period_type=RetrospectivePeriodType.SEMI_ANNUAL, period_key="2026-H1"
        )
        .count()
    )
    assert count == 1


# --- 編集（PATCH、前期の記録が無い初回利用者向けの手動シード） ---


def test_update_monthly_report_creates_row_when_missing(seeded_session):
    """前期の記録が無い初回利用者が、対象月の目標のみを手動入力できる（要件定義書R-83）。"""
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)

    retrospective = work_report_service.update_monthly_report(
        seeded_session, goal, period_key="2026-08", target_goal_text="手動で設定した目標"
    )

    assert retrospective.target_goal_text == "手動で設定した目標"
    assert retrospective.edited_at is not None
    assert "手動で設定した目標" in retrospective.body


def test_update_monthly_report_edits_existing_row_in_place(seeded_session, monkeypatch):
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch, response=_MONTHLY_RESPONSE)
    generated = work_report_service.generate_monthly_report(
        seeded_session, goal, period_key="2026-08", today=dt.date(2026, 9, 5)
    )

    updated = work_report_service.update_monthly_report(
        seeded_session,
        goal,
        period_key="2026-08",
        achievement_score=5,
        business_summary="修正後の業務内容要約",
        achievement_reflection="修正後の振り返り",
        report_notes="修正後の報告連絡事項",
    )

    assert updated.id == generated.id
    assert updated.achievement_score == 5
    assert updated.business_summary == "修正後の業務内容要約"
    assert updated.achievement_reflection == "修正後の振り返り"
    assert updated.report_notes == "修正後の報告連絡事項"
    assert updated.edited_at is not None
    assert "## 目標がどの程度達成されたか\n5" in updated.body
    assert "修正後の業務内容要約" in updated.body
    assert "修正後の振り返り" in updated.body
    assert "修正後の報告連絡事項" in updated.body


def test_update_semiannual_review_creates_row_when_missing(seeded_session):
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)

    retrospective = work_report_service.update_semiannual_review(
        seeded_session, goal, period_key="2026-H1", target_goal_text="手動で設定した半期目標"
    )

    assert retrospective.target_goal_text == "手動で設定した半期目標"
    assert retrospective.edited_at is not None


def test_update_semiannual_review_edits_existing_row_in_place(seeded_session, monkeypatch):
    goal = _make_work_goal(seeded_session)
    _make_work_assignment(seeded_session, goal)
    _stub_send_message(monkeypatch, response=_SEMIANNUAL_RESPONSE)
    generated = work_report_service.generate_semiannual_review(
        seeded_session, goal, period_key="2026-H1", today=dt.date(2026, 8, 20)
    )

    updated = work_report_service.update_semiannual_review(
        seeded_session,
        goal,
        period_key="2026-H1",
        business_summary="修正後の業務内容要約",
        achievement_reflection="修正後の振り返り",
        next_goal_text="修正後の次半期の目標",
    )

    assert updated.id == generated.id
    assert updated.business_summary == "修正後の業務内容要約"
    assert updated.achievement_reflection == "修正後の振り返り"
    assert updated.next_goal_text == "修正後の次半期の目標"
    assert updated.edited_at is not None
    assert "修正後の次半期の目標" in updated.body
