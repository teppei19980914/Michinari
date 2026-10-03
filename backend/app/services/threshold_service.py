"""判定ロジック（設計書 ロジック・プロンプト編 11章）。

警告判定（NT-01）、強制リプラン判定（NT-02）、締切超過判定（NT-06）。
閾値は app_setting から読む（ソースコードへの直接記述禁止、CLAUDE.md）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.constants.app_setting_keys import (
    THRESHOLD_REPLAN_OVERRUN_DAYS,
    THRESHOLD_WARNING_RATIO,
)
from app.constants.enums import DayType
from app.models.material import Material
from app.services import baseline_service, setting_reader


def check_warning(
    session: Session,
    material_id: int,
    today: dt.date,
    today_day_type: DayType,
    quota_today: float,
) -> bool:
    """警告判定 NT-01（11.1）。バッファ日など、PLAN日以外は判定しない。"""
    if today_day_type != DayType.PLAN:
        return False

    baseline = baseline_service.get_current_baseline(session, material_id, today)
    if baseline is None or baseline.baseline_daily_quota <= 0:
        return False

    threshold = setting_reader.get_float(session, THRESHOLD_WARNING_RATIO)
    return (quota_today / baseline.baseline_daily_quota) >= threshold


def check_forced_replan(session: Session, overrun_days: int | None) -> bool:
    """強制リプラン判定 NT-02（11.2）。

    overrun_days が None（speed_eff 算出不能）の場合は判定しない。
    """
    if overrun_days is None:
        return False

    threshold = setting_reader.get_int(session, THRESHOLD_REPLAN_OVERRUN_DAYS)
    return overrun_days > threshold


def check_deadline_overrun(today: dt.date, material: Material, remaining: float) -> bool:
    """締切超過判定 NT-06（11.4）。"""
    return today > material.due_date and remaining > 0 and material.is_active
