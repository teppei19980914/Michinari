"""目標の負荷プロファイルCRUD（設計書データ構造編5.3・6.2、仕様書7.1章）。

共通ガード・CRUDは`goal_service.py`を参照（実装フェーズ分割計画書S02、`goal_service.py`
からの分割）。
"""

import datetime as dt

from sqlalchemy.orm import Session

from app.models.goal import Goal, LoadProfile
from app.services import goal_service
from app.services.exceptions import NotFoundError, ValidationError


def get_load_profile(session: Session, load_profile_id: int) -> LoadProfile:
    profile = session.get(LoadProfile, load_profile_id)
    if profile is None:
        raise NotFoundError("LoadProfile", load_profile_id)
    return profile


def list_load_profiles(session: Session, goal: Goal) -> list[LoadProfile]:
    return (
        session.query(LoadProfile)
        .filter(LoadProfile.goal_id == goal.id)
        .order_by(LoadProfile.date_from)
        .all()
    )


def _validate_load_profile_period(
    session: Session,
    goal: Goal,
    date_from: dt.date,
    date_to: dt.date,
    coefficient: float,
    exclude_id: int | None,
) -> None:
    if date_from > date_to:
        raise ValidationError("Effective start date must be on or before the end date")
    if coefficient <= 0:
        raise ValidationError("Load coefficient must be a positive number")

    query = session.query(LoadProfile).filter(
        LoadProfile.goal_id == goal.id,
        LoadProfile.date_from <= date_to,
        LoadProfile.date_to >= date_from,
    )
    if exclude_id is not None:
        query = query.filter(LoadProfile.id != exclude_id)
    if query.first() is not None:
        raise ValidationError("Period overlaps with an existing load profile")


def create_load_profile(
    session: Session,
    goal: Goal,
    *,
    date_from: dt.date,
    date_to: dt.date,
    coefficient: float,
    note: str | None,
) -> LoadProfile:
    goal_service.ensure_goal_editable(goal)
    _validate_load_profile_period(session, goal, date_from, date_to, coefficient, exclude_id=None)
    profile = LoadProfile(
        goal_id=goal.id, date_from=date_from, date_to=date_to, coefficient=coefficient, note=note
    )
    session.add(profile)
    session.flush()
    return profile


def update_load_profile(
    session: Session,
    profile: LoadProfile,
    *,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    coefficient: float | None = None,
    note: str | None = None,
) -> LoadProfile:
    goal_service.ensure_goal_editable(profile.goal)
    new_from = date_from if date_from is not None else profile.date_from
    new_to = date_to if date_to is not None else profile.date_to
    new_coefficient = coefficient if coefficient is not None else profile.coefficient
    _validate_load_profile_period(
        session, profile.goal, new_from, new_to, new_coefficient, exclude_id=profile.id
    )
    profile.date_from = new_from
    profile.date_to = new_to
    profile.coefficient = new_coefficient
    if note is not None:
        profile.note = note
    session.flush()
    return profile


def delete_load_profile(session: Session, profile: LoadProfile) -> None:
    goal_service.ensure_goal_editable(profile.goal)
    session.delete(profile)
    session.flush()
