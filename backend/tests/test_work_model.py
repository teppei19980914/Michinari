"""完了条件: 仕事目標（category=WORK）のためのモデル（WorkAssignment・WorkLog）と
goal_retrospectiveの定期報告用列が、5.1〜5.4で定義した制約どおりに動作すること
（実装フェーズ分割計画書 Phase 20）。

test_models_crud.py の書籍（Book/ReadingLog）向けテストと同型の観点
（1目標1件のUNIQUE制約、業務記録が残る案件のRESTRICT、goal削除のCASCADE、
(work_assignment_id, daily_record_id)の重複防止）を仕事版として検証する。
"""

import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from app.constants.enums import GoalCategory, GoalStatus, RecordState, RetrospectivePeriodType
from app.models.goal import Goal
from app.models.record import DailyRecord, WorkLog
from app.models.retrospective import GoalRetrospective
from app.models.work import WorkAssignment


def _make_work_goal(name: str, start_date: dt.date) -> Goal:
    return Goal(
        name=name,
        start_date=start_date,
        status=GoalStatus.ACTIVE,
        resource_ratio=0,
        category=GoalCategory.WORK,
    )


def test_goal_category_work_is_usable(db_session):
    """完了条件: GoalCategory.WORKが使えること。"""
    goal = _make_work_goal("仕事目標カテゴリ検証用", dt.date(2026, 9, 1))
    db_session.add(goal)
    db_session.commit()

    assert db_session.get(Goal, goal.id).category == GoalCategory.WORK


def test_work_assignment_and_work_log_crud(db_session):
    goal = _make_work_goal("仕事目標CRUD検証用", dt.date(2026, 9, 1))
    db_session.add(goal)
    db_session.flush()

    assignment = WorkAssignment(
        goal_id=goal.id,
        client_name="株式会社サンプル",
        expected_content="Webサイトのリニューアル案件",
        start_date=dt.date(2026, 9, 1),
    )
    db_session.add(assignment)
    db_session.flush()

    daily_record = DailyRecord(
        record_date=dt.date(2026, 9, 2), record_state=RecordState.REPORTED
    )
    db_session.add(daily_record)
    db_session.flush()

    work_log = WorkLog(
        daily_record_id=daily_record.id,
        work_assignment_id=assignment.id,
        body="要件定義のヒアリングを実施した。",
    )
    db_session.add(work_log)
    db_session.commit()

    assert db_session.get(WorkAssignment, assignment.id).expected_content.startswith(
        "Webサイト"
    )
    assert db_session.get(WorkLog, work_log.id).body.startswith("要件定義")
    assert len(db_session.get(WorkAssignment, assignment.id).work_logs) == 1


def test_work_assignment_cascade_deletes_with_goal(db_session):
    goal = _make_work_goal("goalカスケード検証用仕事目標", dt.date(2026, 9, 1))
    db_session.add(goal)
    db_session.flush()

    assignment = WorkAssignment(
        goal_id=goal.id,
        expected_content="実績なしの案件",
        start_date=dt.date(2026, 9, 1),
    )
    db_session.add(assignment)
    db_session.commit()

    # goal 削除 -> work_assignment が CASCADE で削除されること（work_logの参照がないため成功する）
    db_session.delete(db_session.get(Goal, goal.id))
    db_session.commit()

    assert db_session.get(Goal, goal.id) is None
    assert db_session.get(WorkAssignment, assignment.id) is None


def test_work_assignment_goal_id_unique_constraint(db_session):
    """完了条件: work_assignment.goal_idにUNIQUE制約が効くこと（1目標1案件）。"""
    goal = _make_work_goal("1目標1案件検証用", dt.date(2026, 9, 1))
    db_session.add(goal)
    db_session.flush()

    db_session.add(
        WorkAssignment(
            goal_id=goal.id, expected_content="1件目の案件", start_date=dt.date(2026, 9, 1)
        )
    )
    db_session.commit()

    db_session.add(
        WorkAssignment(
            goal_id=goal.id, expected_content="2件目の案件", start_date=dt.date(2026, 9, 1)
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_work_assignment_delete_restricted_when_work_log_exists(db_session):
    goal = _make_work_goal("RESTRICT検証用仕事目標", dt.date(2026, 9, 1))
    db_session.add(goal)
    db_session.flush()

    assignment = WorkAssignment(
        goal_id=goal.id, expected_content="実績ありの案件", start_date=dt.date(2026, 9, 1)
    )
    db_session.add(assignment)
    db_session.flush()

    daily_record = DailyRecord(
        record_date=dt.date(2026, 9, 3), record_state=RecordState.REPORTED
    )
    db_session.add(daily_record)
    db_session.flush()

    work_log = WorkLog(
        daily_record_id=daily_record.id, work_assignment_id=assignment.id, body="業務記録本文"
    )
    db_session.add(work_log)
    db_session.commit()

    db_session.delete(assignment)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.get(WorkAssignment, assignment.id) is not None


def test_work_log_unique_assignment_and_daily_record(db_session):
    """完了条件: work_logが(work_assignment_id, daily_record_id)単位で一意であること。"""
    goal = _make_work_goal("重複防止検証用仕事目標", dt.date(2026, 9, 1))
    db_session.add(goal)
    db_session.flush()

    assignment = WorkAssignment(
        goal_id=goal.id, expected_content="重複検証用案件", start_date=dt.date(2026, 9, 1)
    )
    db_session.add(assignment)
    db_session.flush()

    daily_record = DailyRecord(
        record_date=dt.date(2026, 9, 4), record_state=RecordState.REPORTED
    )
    db_session.add(daily_record)
    db_session.flush()

    db_session.add(
        WorkLog(daily_record_id=daily_record.id, work_assignment_id=assignment.id, body="1件目")
    )
    db_session.commit()

    db_session.add(
        WorkLog(daily_record_id=daily_record.id, work_assignment_id=assignment.id, body="2件目")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_daily_record_cascade_deletes_work_logs(db_session):
    """work_log は daily_record 削除時に CASCADE で削除されること（study_log/reading_logと
    同じ方針。work_assignment側はRESTRICTのため、daily_record起点の削除で検証する）。
    """
    goal = _make_work_goal("daily_recordカスケード検証用仕事目標", dt.date(2026, 9, 1))
    db_session.add(goal)
    db_session.flush()

    assignment = WorkAssignment(
        goal_id=goal.id, expected_content="daily_record起点カスケード検証案件",
        start_date=dt.date(2026, 9, 1),
    )
    db_session.add(assignment)
    db_session.flush()

    daily_record = DailyRecord(
        record_date=dt.date(2026, 9, 5), record_state=RecordState.REPORTED
    )
    db_session.add(daily_record)
    db_session.flush()

    work_log = WorkLog(
        daily_record_id=daily_record.id, work_assignment_id=assignment.id, body="削除検証用本文"
    )
    db_session.add(work_log)
    db_session.commit()

    db_session.delete(db_session.get(DailyRecord, daily_record.id))
    db_session.commit()

    assert db_session.get(WorkLog, work_log.id) is None
    # work_assignment 自体は daily_record に紐づかないため残る
    assert db_session.get(WorkAssignment, assignment.id) is not None


def test_goal_retrospective_work_columns_save_and_load(db_session):
    """完了条件: goal_retrospectiveに新設列を指定して保存・取得できること
    （period_type=MONTHLY等）。"""
    goal = _make_work_goal("月次報告列検証用", dt.date(2026, 9, 1))
    db_session.add(goal)
    db_session.flush()

    retrospective = GoalRetrospective(
        goal_id=goal.id,
        body="## 業務内容の要約\n...",
        period_type=RetrospectivePeriodType.MONTHLY,
        period_key="2026-09",
        target_goal_text="前月に提案した目標",
        business_summary="業務内容の要約本文",
        achievement_score=3,
        achievement_reflection="振り返り本文",
        next_goal_text="来月の目標案",
        report_notes="",
        edited_at=None,
    )
    db_session.add(retrospective)
    db_session.commit()

    reloaded = db_session.get(GoalRetrospective, retrospective.id)
    assert reloaded.period_type == RetrospectivePeriodType.MONTHLY
    assert reloaded.period_key == "2026-09"
    assert reloaded.target_goal_text == "前月に提案した目標"
    assert reloaded.business_summary == "業務内容の要約本文"
    assert reloaded.achievement_score == 3
    assert reloaded.achievement_reflection == "振り返り本文"
    assert reloaded.next_goal_text == "来月の目標案"
    assert reloaded.report_notes == ""
    assert reloaded.edited_at is None


def test_goal_retrospective_semi_annual_period_type(db_session):
    goal = _make_work_goal("半期評価列検証用", dt.date(2026, 9, 1))
    db_session.add(goal)
    db_session.flush()

    retrospective = GoalRetrospective(
        goal_id=goal.id,
        body="## 業務内容の要約\n...",
        period_type=RetrospectivePeriodType.SEMI_ANNUAL,
        period_key="2026-H2",
    )
    db_session.add(retrospective)
    db_session.commit()

    assert db_session.get(GoalRetrospective, retrospective.id).period_type == (
        RetrospectivePeriodType.SEMI_ANNUAL
    )


def test_goal_retrospective_multiple_period_keys_for_same_goal(db_session):
    """完了条件: goal_retrospectiveにperiod_type／period_keyを指定した複数レコード
    （同一goal・異なるperiod_key）が保存できること。"""
    goal = _make_work_goal("複数期間検証用", dt.date(2026, 9, 1))
    db_session.add(goal)
    db_session.flush()

    db_session.add_all(
        [
            GoalRetrospective(
                goal_id=goal.id,
                body="8月分",
                period_type=RetrospectivePeriodType.MONTHLY,
                period_key="2026-08",
            ),
            GoalRetrospective(
                goal_id=goal.id,
                body="9月分",
                period_type=RetrospectivePeriodType.MONTHLY,
                period_key="2026-09",
            ),
            GoalRetrospective(
                goal_id=goal.id,
                body="H1分",
                period_type=RetrospectivePeriodType.SEMI_ANNUAL,
                period_key="2026-H1",
            ),
        ]
    )
    db_session.commit()

    assert (
        db_session.query(GoalRetrospective).filter_by(goal_id=goal.id).count() == 3
    )


def test_goal_retrospective_work_period_unique_constraint(db_session):
    """完了条件: 同一goal・同一period_type・同一period_key・同一is_anonymizedの組み合わせは
    一意であること（データ構造編5.4「WORKでは常に一意」）。"""
    goal = _make_work_goal("期間一意制約検証用", dt.date(2026, 9, 1))
    db_session.add(goal)
    db_session.flush()

    db_session.add(
        GoalRetrospective(
            goal_id=goal.id,
            body="1件目",
            period_type=RetrospectivePeriodType.MONTHLY,
            period_key="2026-09",
        )
    )
    db_session.commit()

    db_session.add(
        GoalRetrospective(
            goal_id=goal.id,
            body="2件目（重複）",
            period_type=RetrospectivePeriodType.MONTHLY,
            period_key="2026-09",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_goal_retrospective_exam_reading_style_rows_unaffected_by_unique_constraint(db_session):
    """完了条件: 既存のEXAM/READING運用（period_type・period_key共にNULL）が、
    新設のUNIQUE制約導入後も無制限に再生成できること（標準SQLのNULL比較により
    NULL同士は一意制約の対象外となる。データ構造編5.4「制約」）。"""
    goal = _make_work_goal("EXAM_READING互換検証用", dt.date(2026, 9, 1))
    db_session.add(goal)
    db_session.flush()

    # period_type/period_keyを指定しない（EXAM総括レポート・READING読了レポートと同じ形）
    # レコードを同一goalに複数回追加しても、UNIQUE制約に抵触せず保存できること。
    db_session.add_all(
        [
            GoalRetrospective(goal_id=goal.id, body="再生成1回目"),
            GoalRetrospective(goal_id=goal.id, body="再生成2回目"),
            GoalRetrospective(goal_id=goal.id, body="再生成3回目"),
        ]
    )
    db_session.commit()

    assert db_session.query(GoalRetrospective).filter_by(goal_id=goal.id).count() == 3
