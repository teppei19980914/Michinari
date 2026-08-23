"""教材のAPI（データ構造編6.2、実装フェーズ分割計画書Phase3）。

serialize_material は goals.py（目標詳細への教材ネスト表示）からも共通処理として使う
（CLAUDE.md DRYの原則）。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.material import Material
from app.schemas.material import (
    MaterialCycleProgressRead,
    MaterialRead,
    MaterialUpdate,
    SlotCheckRead,
)
from app.services import cycle_service, material_service, metrics_service

router = APIRouter(tags=["materials"])


def serialize_material(session: Session, material: Material) -> MaterialRead:
    """派生値（総作業量・現在周回・残量・進捗率）を都度算出して付与する（CLAUDE.md 保存禁止）。"""
    progress = cycle_service.get_material_progress(session, material)
    current_cycle_progress = cycle_service.compute_current_cycle_progress(material, progress)
    return MaterialRead(
        id=material.id,
        goal_id=material.goal_id,
        name=material.name,
        unit_label=material.unit_label,
        total_amount=material.total_amount,
        planned_cycles=material.planned_cycles,
        subject_ids=[link.subject_id for link in material.subject_links],
        start_date=material.start_date,
        due_date=material.due_date,
        due_date_is_manual=material.due_date_is_manual,
        required_block_minutes=material.required_block_minutes,
        required_environment=material.required_environment,
        quality_metric_type=material.quality_metric_type,
        is_active=material.is_active,
        display_order=material.display_order,
        total_work=progress.total_work,
        current_cycle=progress.current_cycle,
        remaining=progress.remaining,
        completed=progress.completed,
        progress_rate_in_cycle=current_cycle_progress.progress_rate_in_cycle,
        progress_rate=metrics_service.compute_progress_rate(progress),
    )


@router.patch("/materials/{material_id}", response_model=MaterialRead)
def update_material(
    material_id: int, payload: MaterialUpdate, session: Session = Depends(get_db)
) -> MaterialRead:
    material = material_service.get_material(session, material_id)
    material_service.update_material(session, material, **payload.model_dump(exclude_unset=True))
    session.commit()
    return serialize_material(session, material)


@router.delete("/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(material_id: int, session: Session = Depends(get_db)) -> None:
    material = material_service.get_material(session, material_id)
    material_service.delete_material(session, material)
    session.commit()


@router.post("/materials/{material_id}/deactivate", response_model=MaterialRead)
def deactivate_material(material_id: int, session: Session = Depends(get_db)) -> MaterialRead:
    material = material_service.get_material(session, material_id)
    material_service.deactivate_material(session, material)
    session.commit()
    return serialize_material(session, material)


@router.get("/materials/{material_id}/slot-check", response_model=SlotCheckRead)
def get_slot_check(material_id: int, session: Session = Depends(get_db)) -> SlotCheckRead:
    material = material_service.get_material(session, material_id)
    sufficient = material_service.get_slot_sufficiency(session, material)
    return SlotCheckRead(sufficient=sufficient)


@router.get("/materials/{material_id}/cycles", response_model=list[MaterialCycleProgressRead])
def get_cycle_progress(
    material_id: int, session: Session = Depends(get_db)
) -> list[MaterialCycleProgressRead]:
    material = material_service.get_material(session, material_id)
    return [
        MaterialCycleProgressRead(
            cycle_number=p.cycle_number,
            completed_amount=p.completed_amount,
            speed=p.speed,
            sample_count=p.sample_count,
            quality_average=p.quality_average,
        )
        for p in material_service.get_cycle_progress(session, material)
    ]
