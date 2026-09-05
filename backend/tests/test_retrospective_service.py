"""retrospective_service のテスト（データ構造編5.4「最新の総括レポートを取得する
ロジックの拡張」、実装フェーズ分割計画書Phase22）。

生成（generate_retrospective）はAI呼び出しを伴うためAPI層のテスト（test_api_closure.py）
で検証し、ここではperiod_type／period_keyによる絞り込み拡張のみを対象とする
（CLAUDE.md DRYの原則）。
"""

import datetime as dt

import pytest

from app.constants.enums import GoalCategory, GoalStatus, RetrospectivePeriodType
from app.models.goal import Goal
from app.models.retrospective import GoalRetrospective
from app.services import retrospective_service
from app.services.exceptions import ValidationError


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


def test_get_latest_retrospective_without_period_ignores_period_rows(db_session):
    """period_type／period_key未指定（EXAM総括レポート・READING読了レポートの既定挙動）
    では、period_typeが設定されたWORKの行を対象に含めない（回帰防止）。"""
    goal = _make_work_goal(db_session)
    db_session.add(
        GoalRetrospective(
            goal_id=goal.id,
            body="月次報告",
            period_type=RetrospectivePeriodType.MONTHLY,
            period_key="2026-08",
        )
    )
    db_session.flush()

    result = retrospective_service.get_latest_retrospective(db_session, goal)

    assert result is None


def test_get_latest_retrospective_with_period_returns_matching_row(db_session):
    goal = _make_work_goal(db_session)
    db_session.add(
        GoalRetrospective(
            goal_id=goal.id,
            body="2026年7月分",
            period_type=RetrospectivePeriodType.MONTHLY,
            period_key="2026-07",
        )
    )
    db_session.add(
        GoalRetrospective(
            goal_id=goal.id,
            body="2026年8月分",
            period_type=RetrospectivePeriodType.MONTHLY,
            period_key="2026-08",
        )
    )
    db_session.flush()

    result = retrospective_service.get_latest_retrospective(
        db_session, goal, period_type=RetrospectivePeriodType.MONTHLY, period_key="2026-08"
    )

    assert result is not None
    assert result.body == "2026年8月分"


def test_get_latest_retrospective_with_period_distinguishes_semiannual_from_monthly(db_session):
    goal = _make_work_goal(db_session)
    db_session.add(
        GoalRetrospective(
            goal_id=goal.id,
            body="半期評価",
            period_type=RetrospectivePeriodType.SEMI_ANNUAL,
            period_key="2026-H1",
        )
    )
    db_session.flush()

    result = retrospective_service.get_latest_retrospective(
        db_session, goal, period_type=RetrospectivePeriodType.MONTHLY, period_key="2026-H1"
    )

    assert result is None


def test_generate_retrospective_on_work_goal_is_rejected(db_session):
    """恒久的な仕様：仕事目標には総括レポート（EXAM/READING専用）を生成できない
    （読書がPhase15〜16で経由した暫定ガードとは異なる。データ構造編6.2）。"""
    goal = _make_work_goal(db_session)

    with pytest.raises(ValidationError):
        retrospective_service.generate_retrospective(db_session, goal, today=dt.date(2026, 9, 5))
