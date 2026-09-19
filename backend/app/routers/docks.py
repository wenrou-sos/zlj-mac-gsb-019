from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, planner, schemas, serializers
from ..database import get_db

router = APIRouter(prefix="/api/docks", tags=["docks"])


@router.get("", response_model=list[schemas.Dock])
def list_docks(db: Session = Depends(get_db)):
    return [serializers.dock_out(d) for d in db.query(models.Dock).all()]


@router.post("", response_model=schemas.Dock, status_code=201)
def create_dock(payload: schemas.DockCreate, db: Session = Depends(get_db)):
    if db.query(models.Dock).filter_by(name=payload.name).first():
        raise HTTPException(409, "同名坞位已存在")
    dock = models.Dock(**payload.model_dump())
    db.add(dock)
    db.commit()
    db.refresh(dock)
    return serializers.dock_out(dock)


@router.delete("/{dock_id}", status_code=204)
def delete_dock(dock_id: int, db: Session = Depends(get_db)):
    dock = db.get(models.Dock, dock_id)
    if not dock:
        raise HTTPException(404, "坞位不存在")
    db.delete(dock)
    db.commit()


# ---------------------------------------------------------------------------
# Bookings (坞位占用)
# ---------------------------------------------------------------------------


@router.get("/bookings", response_model=list[schemas.Booking])
def list_bookings(db: Session = Depends(get_db)):
    return [serializers.booking_out(b) for b in db.query(models.DockBooking).all()]


@router.post("/bookings", status_code=201)
def create_booking(payload: schemas.BookingCreate, db: Session = Depends(get_db)):
    dock = db.get(models.Dock, payload.dock_id)
    task = db.get(models.Task, payload.task_id)
    if not dock or not task:
        raise HTTPException(404, "坞位或任务不存在")
    try:
        booking, affected, requested_start = planner.create_booking(
            db,
            dock,
            task,
            payload.start_date,
            payload.end_date,
            auto_adjust=payload.auto_adjust,
        )
    except planner.BookingConflictError as exc:
        raise HTTPException(409, str(exc))
    db.commit()
    db.refresh(booking)
    return {
        "booking": serializers.booking_out(booking),
        "affected_tasks": [serializers.task_out(t) for t in affected],
        "moved": requested_start is not None,
        "requested_start": requested_start,
    }


@router.delete("/bookings/{booking_id}", status_code=204)
def delete_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.get(models.DockBooking, booking_id)
    if not booking:
        raise HTTPException(404, "占用记录不存在")
    db.delete(booking)
    db.commit()
