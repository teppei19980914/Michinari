"""日次ノルマの算出（設計書 ロジック・プロンプト編 7章）。

未達分は加算しない。前日の未達は R(m) の増加と P(m) の減少に自然に反映され、
翌日のノルマは緩やかに再配分される（全量繰越ではない、7.2）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.enums import DayType
from app.models.goal import Goal
from app.models.material import Material
from app.services import calendar_service, cycle_service


def compute_material_quota(
    session: Session,
    goal: Goal,
    material: Material,
    today: dt.date,
    treat_holiday_as_buffer: bool,
) -> float:
    """教材の日次ノルマ quota(m, T) を算出する（7.1）。

    今日がPLAN日でない場合、残計画日が0（W(m)=0）の場合、または今日がまだ教材の学習期間
    （開始日〜締切）に入っていない場合は0を返す（例外を発生させない）。学習期間開始前の
    教材は「今日時点では未着手」として一貫して扱い、警告判定・基準値記録・AI向け状況出力の
    いずれにおいても今日のノルマとしては計上しない（この関数を経由する呼び出し元すべてに
    共通適用するため、ここで一元的に判定する）。
    """
    if today < material.start_date:
        return 0.0

    day_types = calendar_service.resolve_day_types(
        session, today, material.due_date, treat_holiday_as_buffer
    )
    if day_types.get(today) != DayType.PLAN:
        return 0.0

    coefficients = calendar_service.resolve_load_coefficients(
        session, goal.id, today, material.due_date
    )
    plan_days = [d for d, day_type in day_types.items() if day_type == DayType.PLAN]
    total_weight = sum(coefficients[d] for d in plan_days)
    if total_weight <= 0:
        return 0.0

    progress = cycle_service.get_material_progress(session, material)
    return progress.remaining * coefficients[today] / total_weight
