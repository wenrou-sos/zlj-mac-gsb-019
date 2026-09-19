from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, planner, schemas, serializers
from ..database import get_db

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[schemas.Project])
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(models.Project).order_by(models.Project.start_date).all()
    return [serializers.project_out(p) for p in projects]


@router.post("", response_model=schemas.Project, status_code=201)
def create_project(payload: schemas.ProjectCreate, db: Session = Depends(get_db)):
    project = models.Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return serializers.project_out(project)


@router.get("/{project_id}", response_model=schemas.Project)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return serializers.project_out(project)


@router.patch("/{project_id}", response_model=schemas.Project)
def update_project(
    project_id: int, payload: schemas.ProjectUpdate, db: Session = Depends(get_db)
):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return serializers.project_out(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    db.delete(project)
    db.commit()


@router.post("/{project_id}/recompute")
def recompute_project(project_id: int, db: Session = Depends(get_db)):
    """Re-evaluate blockers and the dock period for the whole project."""
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    planner.recompute(db)
    db.commit()
    return {"ok": True}
