from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, planner, schemas, serializers
from ..database import get_db

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _apply_relations(db: Session, task: models.Task, payload) -> None:
    if payload.depends_on is not None:
        deps = (
            db.query(models.Task)
            .filter(
                models.Task.id.in_(payload.depends_on),
                models.Task.project_id == task.project_id,
            )
            .all()
        )
        if len(deps) != len(set(payload.depends_on)):
            raise HTTPException(400, "依赖任务不存在或不属于同一项目")
        if task.id in payload.depends_on:
            raise HTTPException(400, "任务不能依赖自身")
        task.dependencies = deps

    if payload.team_ids is not None:
        teams = (
            db.query(models.Team).filter(models.Team.id.in_(payload.team_ids)).all()
        )
        if len(teams) != len(set(payload.team_ids)):
            raise HTTPException(400, "部分施工队不存在")
        task.teams = teams


@router.get("", response_model=list[schemas.Task])
def list_tasks(project_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Task)
    if project_id is not None:
        query = query.filter(models.Task.project_id == project_id)
    tasks = query.order_by(models.Task.start_date).all()
    return [serializers.task_out(t) for t in tasks]


@router.post("", response_model=schemas.Task, status_code=201)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)):
    project = db.get(models.Project, payload.project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    data = payload.model_dump(exclude={"depends_on", "team_ids"})
    task = models.Task(**data)
    db.add(task)
    db.flush()
    _apply_relations(db, task, payload)
    db.commit()
    db.refresh(task)
    planner.recompute(db)
    db.commit()
    db.refresh(task)
    return serializers.task_out(task)


@router.get("/{task_id}", response_model=schemas.Task)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return serializers.task_out(task)


@router.patch("/{task_id}", response_model=schemas.Task)
def update_task(
    task_id: int, payload: schemas.TaskUpdate, db: Session = Depends(get_db)
):
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    data = payload.model_dump(
        exclude_unset=True, exclude={"depends_on", "team_ids"}
    )
    new_start = data.get("start_date", task.start_date)
    new_end = data.get("end_date", task.end_date)
    if new_end < new_start:
        raise HTTPException(400, "end_date 不能早于 start_date")

    for key, value in data.items():
        setattr(task, key, value)
    _apply_relations(db, task, payload)
    db.flush()
    planner.recompute(db)
    db.commit()
    db.refresh(task)
    return serializers.task_out(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    db.delete(task)
    db.commit()


@router.post("/{task_id}/delay")
def report_delay(
    task_id: int, payload: schemas.TaskDelay, db: Session = Depends(get_db)
):
    """Report an on-site delay. Downstream tasks are moved automatically."""
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if payload.days <= 0:
        raise HTTPException(400, "延期天数必须大于 0")
    moved = planner.task_delayed(db, task, payload.days)
    db.commit()
    db.refresh(task)
    return {
        "task": serializers.task_out(task),
        "affected_tasks": [serializers.task_out(t) for t in moved],
        "count": len(moved),
    }
