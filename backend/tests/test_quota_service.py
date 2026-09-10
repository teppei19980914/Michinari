"""quota_service のテスト（ロジック・プロンプト編 7章、20章の検証観点）。

Phase2必須観点のうち「残量再配分」「バッファ非対称性」「負荷係数」「境界値」を中心に検証する。
"""

import datetime as dt

import pytest

from app.constants.enums import DayType, GoalStatus, RecordState
from app.models.goal import Goal, LoadProfile
from app.models.material import Material
from app.models.record import DailyRecord, StudyLog
from app.models.setting import CalendarDayOverride
from app.services import cycle_service, quota_service


def _make_goal(db_session) -> Goal:
    goal = Goal(
        name="ノルマ検証",
        start_date=dt.date(2026, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    db_session.add(goal)
    db_session.flush()
    return goal


def _make_material(db_session, goal_id: int, total_amount: float, due_date: dt.date) -> Material:
    material = Material(
        goal_id=goal_id,
        name="教材",
        unit_label="問",
        total_amount=total_amount,
        planned_cycles=1,
        start_date=dt.date(2026, 1, 1),
        due_date=due_date,
        display_order=1,
    )
    db_session.add(material)
    db_session.flush()
    return material


def _override_all_plan(
    db_session,
    date_from: dt.date,
    date_to: dt.date,
    exceptions: dict[dt.date, DayType] | None = None,
) -> None:
    """検証を単純化するため、対象期間の全日を個別上書きする（曜日既定に依存しない）。

    exceptions に指定した日はPLAN以外の日種別で上書きする。
    """
    exceptions = exceptions or {}
    d = date_from
    while d <= date_to:
        db_session.add(CalendarDayOverride(target_date=d, day_type=exceptions.get(d, DayType.PLAN)))
        d += dt.timedelta(days=1)


def _record_progress(db_session, material_id: int, record_date: dt.date, amount: float) -> None:
    record = DailyRecord(record_date=record_date, exam_record_state=RecordState.PROGRESS_ONLY)
    db_session.add(record)
    db_session.flush()
    db_session.add(
        StudyLog(
            daily_record_id=record.id,
            material_id=material_id,
            minutes_spent=60,
            amount_completed=amount,
            cycle_number=1,
        )
    )
    db_session.flush()


def test_quota_is_zero_when_today_is_not_plan_day(db_session):
    """バッファ日のノルマが0になること（Phase2必須観点: バッファ非対称性）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, due_date=dt.date(2026, 1, 10))
    db_session.add(CalendarDayOverride(target_date=dt.date(2026, 1, 5), day_type=DayType.BUFFER))
    db_session.flush()

    quota = quota_service.compute_material_quota(
        db_session, goal, material, dt.date(2026, 1, 5), treat_holiday_as_buffer=True
    )

    assert quota == 0.0


def test_buffer_day_without_study_does_not_inflate_next_day_quota(db_session):
    """バッファ日に実績が無くても翌日のノルマが増えないこと（Phase2必須観点: バッファ非対称性）。

    残量再配分方式には「未達の負債」という概念自体が存在しないため、バッファ日を無学習で
    通過しても、翌日のノルマは単純に remaining / 残りPLAN日数 のままであり、
    上乗せされないことを厳密な期待値と比較して確認する。
    """
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=90, due_date=dt.date(2026, 1, 10))
    _override_all_plan(
        db_session,
        dt.date(2026, 1, 1),
        dt.date(2026, 1, 10),
        exceptions={dt.date(2026, 1, 5): DayType.BUFFER},
    )
    db_session.flush()

    quota_after_buffer = quota_service.compute_material_quota(
        db_session, goal, material, dt.date(2026, 1, 6), treat_holiday_as_buffer=True
    )

    # 1/6〜1/10の5日がすべてPLAN、remainingは90のまま（学習実績なし）
    assert quota_after_buffer == pytest.approx(90 / 5)


def test_buffer_day_study_reduces_next_day_quota(db_session):
    """バッファ日に実績があると翌日のノルマが減ること（Phase2必須観点: バッファ非対称性）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=90, due_date=dt.date(2026, 1, 10))
    _override_all_plan(
        db_session,
        dt.date(2026, 1, 1),
        dt.date(2026, 1, 10),
        exceptions={dt.date(2026, 1, 5): DayType.BUFFER},
    )
    db_session.flush()

    quota_without_study = quota_service.compute_material_quota(
        db_session, goal, material, dt.date(2026, 1, 6), treat_holiday_as_buffer=True
    )

    _record_progress(db_session, material.id, dt.date(2026, 1, 5), amount=10)

    quota_with_study = quota_service.compute_material_quota(
        db_session, goal, material, dt.date(2026, 1, 6), treat_holiday_as_buffer=True
    )

    # remaining が 90 -> 80 に減るため、80/5 = 16 < 90/5 = 18
    assert quota_with_study == pytest.approx(80 / 5)
    assert quota_with_study < quota_without_study


def test_quota_reallocation_after_seven_days_of_underachievement(db_session):
    """7日連続未達時、全量繰越（8倍）ではなく再配分（約2.2倍）になること（Phase2必須観点）。

    設計書 7.2 の数値例（初日10、7日未達で約22＝約2.2倍）を再現できる
    残計画日数13日・総量130の構成で検証する（130/13=10、130/6≒21.67）。
    """
    goal = _make_goal(db_session)
    due_date = dt.date(2026, 1, 13)
    material = _make_material(db_session, goal.id, total_amount=130, due_date=due_date)
    _override_all_plan(db_session, dt.date(2026, 1, 1), due_date)
    db_session.flush()

    initial_quota = quota_service.compute_material_quota(
        db_session, goal, material, dt.date(2026, 1, 1), treat_holiday_as_buffer=True
    )
    assert initial_quota == pytest.approx(10.0)

    # 1/1〜1/7の7日間、実績を記録せず未達のまま経過し、1/8時点でノルマを再評価する
    quota_after_seven_underachieved_days = quota_service.compute_material_quota(
        db_session, goal, material, dt.date(2026, 1, 8), treat_holiday_as_buffer=True
    )

    assert quota_after_seven_underachieved_days == pytest.approx(130 / 6)
    ratio = quota_after_seven_underachieved_days / initial_quota
    assert ratio == pytest.approx(2.2, rel=0.05)
    assert ratio < 8.0  # 全量繰越（8倍）ではないことの明示的な反証


def test_quota_zero_when_total_weight_is_zero(db_session):
    """境界値: 負荷係数が0でW(m)が0となる場合に例外が発生しないこと（7.2）。"""
    goal = _make_goal(db_session)
    due_date = dt.date(2026, 1, 3)
    material = _make_material(db_session, goal.id, total_amount=100, due_date=due_date)
    _override_all_plan(db_session, dt.date(2026, 1, 1), due_date)
    db_session.add(
        LoadProfile(
            goal_id=goal.id, date_from=dt.date(2026, 1, 1), date_to=due_date, coefficient=0.0
        )
    )
    db_session.flush()

    quota = quota_service.compute_material_quota(
        db_session, goal, material, dt.date(2026, 1, 1), treat_holiday_as_buffer=True
    )

    assert quota == 0.0


def test_quota_zero_when_today_is_before_start_date(db_session):
    """境界値: 今日がまだ教材の学習期間（開始日）に入っていない場合は0を返すこと。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, due_date=dt.date(2026, 1, 10))
    material.start_date = dt.date(2026, 1, 5)
    db_session.flush()
    _override_all_plan(db_session, dt.date(2026, 1, 1), dt.date(2026, 1, 10))
    db_session.flush()

    quota = quota_service.compute_material_quota(
        db_session, goal, material, dt.date(2026, 1, 3), treat_holiday_as_buffer=True
    )

    assert quota == 0.0


def test_quota_zero_when_no_plan_days_remain_before_deadline(db_session):
    """境界値: 残計画日が0の場合に例外が発生しないこと（締切超過状態でノルマ0）。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=100, due_date=dt.date(2026, 1, 5))

    quota = quota_service.compute_material_quota(
        db_session, goal, material, dt.date(2026, 1, 10), treat_holiday_as_buffer=True
    )

    assert quota == 0.0


def test_quota_zero_when_zero_study_logs_and_deadline_today(db_session):
    """境界値: 実績0件のケースで例外が発生しないこと。"""
    goal = _make_goal(db_session)
    material = _make_material(db_session, goal.id, total_amount=50, due_date=dt.date(2026, 1, 1))
    _override_all_plan(db_session, dt.date(2026, 1, 1), dt.date(2026, 1, 1))
    db_session.flush()

    quota = quota_service.compute_material_quota(
        db_session, goal, material, dt.date(2026, 1, 1), treat_holiday_as_buffer=True
    )

    assert quota == pytest.approx(50.0)


def test_load_coefficient_change_redistributes_quota_without_changing_total_work(db_session):
    """負荷係数を変更しても総量が保存されること（Phase2必須観点）。

    今日自身の係数は1.0に固定し、未来日の係数のみを下げる。分子（今日の係数）が同一のまま
    分母W(m)だけが縮小し、今日のノルマが上がることを確認する。総作業量・残量は係数と無関係に
    保存されることも併せて確認する。
    """
    goal = _make_goal(db_session)
    due_date = dt.date(2026, 1, 4)
    material_uniform = _make_material(db_session, goal.id, total_amount=100, due_date=due_date)
    _override_all_plan(db_session, dt.date(2026, 1, 1), due_date)
    db_session.flush()

    quota_uniform = quota_service.compute_material_quota(
        db_session, goal, material_uniform, dt.date(2026, 1, 1), treat_holiday_as_buffer=True
    )
    assert quota_uniform == pytest.approx(100 / 4)  # W(m) = 1+1+1+1 = 4

    material_reduced_future = _make_material(
        db_session, goal.id, total_amount=100, due_date=due_date
    )
    db_session.add(
        LoadProfile(
            goal_id=goal.id,
            date_from=dt.date(2026, 1, 3),
            date_to=due_date,
            coefficient=0.5,
        )
    )
    db_session.flush()

    quota_reduced_future = quota_service.compute_material_quota(
        db_session, goal, material_reduced_future, dt.date(2026, 1, 1), treat_holiday_as_buffer=True
    )
    # W(m) = 1(1/1) + 1(1/2) + 0.5(1/3) + 0.5(1/4) = 3.0 -> quota = 100/3
    assert quota_reduced_future == pytest.approx(100 / 3)
    assert quota_reduced_future > quota_uniform  # 未来の負荷を下げた分、今日の配分が増える

    # 総作業量（TW(m)）は負荷係数と無関係に保存される
    progress = cycle_service.get_material_progress(db_session, material_reduced_future)
    assert progress.total_work == 100
    assert progress.remaining == 100
