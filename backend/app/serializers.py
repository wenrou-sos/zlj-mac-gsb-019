"""Convert ORM objects into plain dicts for API responses."""

from . import models


def project_out(p: models.Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "ship_name": p.ship_name,
        "start_date": p.start_date,
        "end_date": p.end_date,
        "status": p.status,
        "notes": p.notes or "",
        "created_at": p.created_at,
        "tasks": [task_out(t) for t in p.tasks],
    }


def task_out(t: models.Task) -> dict:
    return {
        "id": t.id,
        "project_id": t.project_id,
        "name": t.name,
        "start_date": t.start_date,
        "end_date": t.end_date,
        "progress": t.progress,
        "status": t.status,
        "blockers": t.blockers or "",
        "depends_on": [d.id for d in t.dependencies],
        "team_ids": [team.id for team in t.teams],
        "parts": [part_out(p) for p in t.parts],
        "bookings": [booking_out(b) for b in t.bookings],
    }


def team_out(team: models.Team) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "specialty": team.specialty,
        "size": team.size,
        "task_ids": [t.id for t in team.tasks],
    }


def part_out(part: models.Part) -> dict:
    return {
        "id": part.id,
        "task_id": part.task_id,
        "name": part.name,
        "quantity": part.quantity,
        "eta": part.eta,
        "arrived": part.arrived,
        "arrived_at": part.arrived_at,
    }


def dock_out(dock: models.Dock) -> dict:
    return {"id": dock.id, "name": dock.name, "capacity": dock.capacity}


def booking_out(b: models.DockBooking) -> dict:
    return {
        "id": b.id,
        "dock_id": b.dock_id,
        "task_id": b.task_id,
        "start_date": b.start_date,
        "end_date": b.end_date,
    }


def log_out(entry: models.ActivityLog) -> dict:
    return {
        "id": entry.id,
        "created_at": entry.created_at,
        "kind": entry.kind,
        "message": entry.message,
    }
