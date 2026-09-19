"""Planning engine.

Responsibilities:
  * detect blockers (missing spare parts, construction-team double booking,
    dock occupancy conflicts),
  * cascade schedule changes through finish-to-start task dependencies,
  * automatically reschedule around delayed parts / busy docks,
  * keep the project dock period (坞期) end date in sync.
"""

import json
from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import models


# ---------------------------------------------------------------------------
# Blocker helpers (stored as a small JSON document in Task.blockers)
# ---------------------------------------------------------------------------


def _get_blockers(task: models.Task) -> dict:
    if not task.blockers:
        return {}
    try:
        return json.loads(task.blockers)
    except (ValueError, TypeError):
        return {}


def _set_blocker(task: models.Task, key: str, reason: str) -> None:
    blockers = _get_blockers(task)
    blockers[key] = reason
    task.blockers = json.dumps(blockers, ensure_ascii=False)
    _refresh_status(task)


def _clear_blocker(task: models.Task, key: str) -> None:
    blockers = _get_blockers(task)
    if key in blockers:
        del blockers[key]
        task.blockers = json.dumps(blockers, ensure_ascii=False)
        _refresh_status(task)


def _refresh_status(task: models.Task) -> None:
    has_blockers = bool(_get_blockers(task))
    if task.status == "done":
        return
    if has_blockers:
        task.status = "blocked"
    elif task.status == "blocked":
        task.status = "pending" if task.progress == 0 else "in_progress"


def log(db: Session, kind: str, message: str) -> models.ActivityLog:
    entry = models.ActivityLog(kind=kind, message=message)
    db.add(entry)
    return entry


def _overlap(s1: date, e1: date, s2: date, e2: date) -> bool:
    """Date intervals are inclusive on both ends."""
    return s1 <= e2 and s2 <= e1


# ---------------------------------------------------------------------------
# Full recomputation: blockers + project status / dock period
# ---------------------------------------------------------------------------


def recompute(db: Session) -> None:
    tasks = db.query(models.Task).all()

    # --- spare parts -------------------------------------------------------
    for task in tasks:
        if task.status == "done":
            _clear_blocker(task, "parts")
            continue
        missing = []
        for part in task.parts:
            if part.arrived:
                continue
            if part.eta is None:
                missing.append(f"{part.name} x{part.quantity}(到货日期未定)")
            elif part.eta >= task.start_date:
                # Part is not in hand before the work starts -> blocked.
                missing.append(
                    f"{part.name} x{part.quantity}(预计 {part.eta.isoformat()} 到货)"
                )
        if missing:
            _set_blocker(task, "parts", "缺件: " + "; ".join(missing))
        else:
            _clear_blocker(task, "parts")

    # --- construction team rostering conflicts -----------------------------
    for task in tasks:
        _clear_blocker(task, "team")
    teams = db.query(models.Team).all()
    for team in teams:
        active = [t for t in team.tasks if t.status != "done"]
        for i, t1 in enumerate(active):
            for t2 in active[i + 1 :]:
                if _overlap(t1.start_date, t1.end_date, t2.start_date, t2.end_date):
                    reason = (
                        f"施工队冲突: {team.name} 在 {t2.start_date.isoformat()}~"
                        f"{t2.end_date.isoformat()} 同时承担「{t2.name}」"
                    )
                    _set_blocker(t1, "team", reason)
                    reason2 = (
                        f"施工队冲突: {team.name} 在 {t1.start_date.isoformat()}~"
                        f"{t1.end_date.isoformat()} 同时承担「{t1.name}」"
                    )
                    _set_blocker(t2, "team", reason2)

    # --- dock occupancy conflicts ------------------------------------------
    for task in tasks:
        _clear_blocker(task, "dock")
    docks = db.query(models.Dock).all()
    for dock in docks:
        bookings = [b for b in dock.bookings if b.task.status != "done"]
        for i, b1 in enumerate(bookings):
            for b2 in bookings[i + 1 :]:
                if _overlap(b1.start_date, b1.end_date, b2.start_date, b2.end_date):
                    _set_blocker(
                        b1.task,
                        "dock",
                        f"坞位冲突: {dock.name} 与「{b2.task.name}」"
                        f"({b2.start_date.isoformat()}~{b2.end_date.isoformat()}) 占用重叠",
                    )
                    _set_blocker(
                        b2.task,
                        "dock",
                        f"坞位冲突: {dock.name} 与「{b1.task.name}」"
                        f"({b1.start_date.isoformat()}~{b1.end_date.isoformat()}) 占用重叠",
                    )

    # --- tasks waiting on blocked upstream work ----------------------------
    # A task whose dependency chain contains a blocked task is itself marked
    # as affected ("受影响任务"), even though dates were already shifted.
    for task in tasks:
        _clear_blocker(task, "upstream")

    def _chain_has_blocker(t: models.Task, stack: set[int]) -> bool:
        if t.status == "done":
            return False
        if t.id in stack:
            return False  # defensive: dependency graph is a DAG
        if _get_blockers(t):
            return True
        stack.add(t.id)
        try:
            return any(_chain_has_blocker(d, stack) for d in t.dependencies)
        finally:
            stack.discard(t.id)

    for task in tasks:
        if task.status == "done":
            continue
        waiting_on = [
            d.name for d in task.dependencies if _chain_has_blocker(d, {task.id})
        ]
        if waiting_on:
            _set_blocker(
                task,
                "upstream",
                "等待上游任务: " + "、".join(f"「{n}」" for n in waiting_on),
            )

    # --- project status + dock period extension ----------------------------
    for project in db.query(models.Project).all():
        if project.tasks:
            max_end = max(t.end_date for t in project.tasks)
            if max_end > project.end_date:
                log(
                    db,
                    "adjustment",
                    f"项目「{project.name}」坞期由 {project.end_date.isoformat()} "
                    f"顺延至 {max_end.isoformat()}",
                )
                project.end_date = max_end
            if all(t.status == "done" for t in project.tasks):
                project.status = "completed"
            elif any(_get_blockers(t) for t in project.tasks):
                project.status = "delayed"
            elif any(t.status == "in_progress" or t.progress > 0 for t in project.tasks):
                project.status = "in_progress"
            else:
                project.status = "planned"


# ---------------------------------------------------------------------------
# Task shifting with dependency cascade
# ---------------------------------------------------------------------------


def shift_task(
    db: Session,
    task: models.Task,
    new_start: date,
    reason: str,
    _moved: dict | None = None,
) -> dict[int, models.Task]:
    """Move a task (and its dock bookings) to start no earlier than new_start.

    Every finish-to-start successor that would overlap the new end date is
    pushed out recursively. Returns {task_id: task} of every moved task.
    """
    if _moved is None:
        _moved = {}
    if task.id in _moved:
        return _moved  # cycle guard (dependency graph should be a DAG)

    delta = (new_start - task.start_date).days
    if delta < 0:
        # Automatic scheduling only moves work later, never earlier.
        return _moved
    if delta > 0:
        task.start_date += timedelta(days=delta)
        task.end_date += timedelta(days=delta)
        for booking in task.bookings:
            booking.start_date += timedelta(days=delta)
            booking.end_date += timedelta(days=delta)
        log(
            db,
            "adjustment",
            f"任务「{task.name}」因{reason}顺延 {delta} 天: "
            f"{task.start_date.isoformat()} ~ {task.end_date.isoformat()}",
        )
    _moved[task.id] = task

    for successor in task.dependents:
        if successor.id in _moved or successor.status == "done":
            continue
        # Finish-to-start: successor may begin exactly when predecessor ends.
        if successor.start_date < task.end_date:
            shift_task(db, successor, task.end_date, f"上游「{task.name}」延期", _moved)
    return _moved


# ---------------------------------------------------------------------------
# Domain events
# ---------------------------------------------------------------------------


def part_changed(db: Session, part: models.Part) -> list[models.Task]:
    """Handle spare part ETA / arrival changes.

    A delayed part pushes the affected task (and its downstream chain) to the
    day after arrival; all blocker markers are then refreshed.
    """
    task = part.task
    moved: dict[int, models.Task] = {}
    if (
        not part.arrived
        and part.eta is not None
        and part.eta >= task.start_date
    ):
        # Work is scheduled to start on the arrival day; recompute() keeps the
        # "waiting for parts" blocker until the part is marked as arrived.
        new_start = part.eta
        moved = shift_task(
            db,
            task,
            new_start,
            reason=f"备件「{part.name}」延期到货({part.eta.isoformat()})",
        )
    recompute(db)
    return list(moved.values())


def task_delayed(db: Session, task: models.Task, days: int) -> list[models.Task]:
    """Report a delay of N days and cascade it through the plan."""
    moved = shift_task(
        db,
        task,
        task.start_date + timedelta(days=days),
        reason="现场延期上报",
    )
    recompute(db)
    return list(moved.values())


def next_free_dock_slot(
    db: Session,
    dock: models.Dock,
    start: date,
    duration_days: int,
    exclude_booking_id: int | None = None,
) -> date:
    """Earliest start date on which the dock is free for the whole interval."""
    candidate = start
    for _ in range(1000):
        end = candidate + timedelta(days=duration_days)
        conflicts = [
            b
            for b in dock.bookings
            if b.id != exclude_booking_id
            and b.task.status != "done"
            and _overlap(b.start_date, b.end_date, candidate, end)
        ]
        if not conflicts:
            return candidate
        candidate = max(b.end_date for b in conflicts) + timedelta(days=1)
    raise RuntimeError("无法找到可用坞位窗口")


def create_booking(
    db: Session,
    dock: models.Dock,
    task: models.Task,
    start: date,
    end: date,
    auto_adjust: bool = True,
) -> tuple[models.DockBooking, list[models.Task], date | None]:
    """Create a dock occupancy, auto-resolving conflicts.

    Returns (booking, affected_tasks, requested_start). requested_start is
    returned (non-None) when the booking had to be moved.
    """
    duration = (end - start).days
    conflicts = [
        b
        for b in dock.bookings
        if b.task.status != "done" and _overlap(b.start_date, b.end_date, start, end)
    ]
    requested_start = None
    moved: dict[int, models.Task] = {}
    if conflicts:
        if not auto_adjust:
            raise BookingConflictError(dock, conflicts)
        requested_start = start
        start = next_free_dock_slot(db, dock, start, duration)
        end = start + timedelta(days=duration)
        log(
            db,
            "warning",
            f"坞位 {dock.name} 在 {requested_start.isoformat()} 被占用, "
            f"任务「{task.name}」自动改约至 {start.isoformat()} ~ {end.isoformat()}",
        )
        if start > task.start_date:
            moved = shift_task(db, task, start, reason=f"等待 {dock.name} 坞位")
        # The task may have moved while cascading; clamp the booking window to
        # the resolved slot instead of creating it before shifting (which
        # would otherwise shift the new booking a second time).

    booking = models.DockBooking(
        dock_id=dock.id, task_id=task.id, start_date=start, end_date=end
    )
    db.add(booking)
    db.flush()

    recompute(db)
    return booking, list(moved.values()), requested_start


class BookingConflictError(Exception):
    def __init__(self, dock: models.Dock, conflicts: list[models.DockBooking]):
        self.dock = dock
        self.conflicts = conflicts
        dates = ", ".join(
            f"「{b.task.name}」{b.start_date.isoformat()}~{b.end_date.isoformat()}"
            for b in conflicts
        )
        super().__init__(f"坞位 {dock.name} 该时段已被占用: {dates}")
