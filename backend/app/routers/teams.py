from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, planner, schemas, serializers
from ..database import get_db

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("", response_model=list[schemas.Team])
def list_teams(db: Session = Depends(get_db)):
    teams = db.query(models.Team).order_by(models.Team.name).all()
    return [serializers.team_out(t) for t in teams]


@router.post("", response_model=schemas.Team, status_code=201)
def create_team(payload: schemas.TeamCreate, db: Session = Depends(get_db)):
    if db.query(models.Team).filter_by(name=payload.name).first():
        raise HTTPException(409, "同名施工队已存在")
    team = models.Team(**payload.model_dump())
    db.add(team)
    db.commit()
    db.refresh(team)
    return serializers.team_out(team)


@router.delete("/{team_id}", status_code=204)
def delete_team(team_id: int, db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(404, "施工队不存在")
    db.delete(team)
    db.commit()


@router.post("/assign", response_model=schemas.Task)
def assign_team(task_id: int, team_id: int, db: Session = Depends(get_db)):
    """Roster a construction team onto a task and re-check overlaps."""
    task = db.get(models.Task, task_id)
    team = db.get(models.Team, team_id)
    if not task or not team:
        raise HTTPException(404, "任务或施工队不存在")
    if team not in task.teams:
        task.teams.append(team)
        db.flush()
    planner.recompute(db)
    db.commit()
    db.refresh(task)
    return serializers.task_out(task)
