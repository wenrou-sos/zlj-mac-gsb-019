import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, serializers
from ..database import get_db

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=schemas.DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    tasks = db.query(models.Task).all()
    blocked = 0
    delayed_parts = 0
    for t in tasks:
        try:
            blockers = json.loads(t.blockers) if t.blockers else {}
        except (ValueError, TypeError):
            blockers = {}
        if blockers:
            blocked += 1
        for p in t.parts:
            if not p.arrived and p.eta is not None and p.eta >= t.start_date:
                delayed_parts += 1

    dock_conflicts = 0
    for dock in db.query(models.Dock).all():
        bookings = [b for b in dock.bookings if b.task.status != "done"]
        for i, b1 in enumerate(bookings):
            for b2 in bookings[i + 1 :]:
                if b1.start_date <= b2.end_date and b2.start_date <= b1.end_date:
                    dock_conflicts += 1

    return {
        "project_count": db.query(models.Project).count(),
        "task_count": len(tasks),
        "blocked_task_count": blocked,
        "delayed_part_count": delayed_parts,
        "dock_count": db.query(models.Dock).count(),
        "team_count": db.query(models.Team).count(),
        "booking_conflict_count": dock_conflicts,
    }


@router.get("/logs", response_model=list[schemas.ActivityLogOut])
def list_logs(limit: int = 50, db: Session = Depends(get_db)):
    entries = (
        db.query(models.ActivityLog)
        .order_by(models.ActivityLog.created_at.desc(), models.ActivityLog.id.desc())
        .limit(min(limit, 500))
        .all()
    )
    return [serializers.log_out(e) for e in entries]
