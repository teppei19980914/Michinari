"""週次要約（WeeklySummary）をテストから組み立てるための共通処理（G4、開発Todo S06）。

資格試験・読書・仕事の3カテゴリのテストで同じ組み立てが必要になるため、diary_helpers.py・
reading_helpers.pyと同じ位置づけでここへ集約する（CLAUDE.md DRYの原則）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.models.record import WeeklySummary


def make_weekly_summary(
    session: Session,
    goal: Goal,
    week_start: dt.date,
    week_end: dt.date | None = None,
    **overrides,
) -> WeeklySummary:
    """週次要約を1件作成する。is_anonymized=Trueを渡せば匿名化版として作成できる。"""
    defaults = dict(
        goal_id=goal.id,
        week_start_date=week_start,
        week_end_date=week_end or week_start + dt.timedelta(days=6),
        summary_body="既に生成済み",
    )
    defaults.update(overrides)
    summary = WeeklySummary(**defaults)
    session.add(summary)
    session.flush()
    return summary
