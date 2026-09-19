from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, planner, schemas, serializers
from ..database import get_db

router = APIRouter(prefix="/api/parts", tags=["parts"])


@router.get("", response_model=list[schemas.Part])
def list_parts(task_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Part)
    if task_id is not None:
        query = query.filter(models.Part.task_id == task_id)
    return [serializers.part_out(p) for p in query.all()]


@router.post("", response_model=schemas.Part, status_code=201)
def create_part(payload: schemas.PartCreate, db: Session = Depends(get_db)):
    task = db.get(models.Task, payload.task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    part = models.Part(**payload.model_dump())
    db.add(part)
    db.flush()
    # A part whose ETA already misses the task start replans immediately.
    planner.part_changed(db, part)
    db.commit()
    db.refresh(part)
    return serializers.part_out(part)


@router.patch("/{part_id}")
def update_part(
    part_id: int, payload: schemas.PartUpdate, db: Session = Depends(get_db)
):
    """Update a part (new ETA / arrival). Triggers automatic replanning:

    * delayed ETA  -> affected task + downstream chain pushed out,
    * marked arrived -> part blocker cleared.
    """
    part = db.get(models.Part, part_id)
    if not part:
        raise HTTPException(404, "备件不存在")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(part, key, value)
    if data.get("arrived"):
        part.arrived_at = date.today()
    db.flush()

    affected = planner.part_changed(db, part)
    db.commit()
    db.refresh(part)
    return {
        "part": serializers.part_out(part),
        "affected_tasks": [serializers.task_out(t) for t in affected],
        "count": len(affected),
    }


@router.delete("/{part_id}", status_code=204)
def delete_part(part_id: int, db: Session = Depends(get_db)):
    part = db.get(models.Part, part_id)
    if not part:
        raise HTTPException(404, "备件不存在")
    db.delete(part)
    db.commit()
