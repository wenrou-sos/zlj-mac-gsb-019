from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models import models as m
from app.schemas import schemas as s
from app.services.scheduling import find_dock_conflicts, recalculate_project

router = APIRouter(prefix="/api")


def _get_project(db: Session, project_id: int) -> m.Project:
    project = db.get(m.Project, project_id)
    if project is None:
        raise HTTPException(404, "项目不存在")
    return project


def _get_task(db: Session, project_id: int, task_id: int) -> m.Task:
    task = db.get(m.Task, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(404, "任务不存在")
    return task


def _load_project_graph(db: Session, project_id: int) -> m.Project:
    stmt = (
        select(m.Project)
        .where(m.Project.id == project_id)
        .options(
            selectinload(m.Project.tasks)
            .selectinload(m.Task.depends_on),
            selectinload(m.Project.tasks)
            .selectinload(m.Task.assignments)
            .selectinload(m.TeamAssignment.team),
            selectinload(m.Project.tasks).selectinload(m.Task.parts),
            selectinload(m.Project.parts),
            selectinload(m.Project.occupancies).selectinload(m.DockOccupancy.dock),
            selectinload(m.Project.dock),
        )
    )
    project = db.scalar(stmt)
    if project is None:
        raise HTTPException(404, "项目不存在")
    return project


# ===========================================================================
# 仪表盘
# ===========================================================================

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    def count(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(*where))

    blocked = db.scalars(
        select(m.Task).where(m.Task.status == m.TASK_BLOCKED)
    ).all()
    delayed_parts = db.scalars(
        select(m.SparePart).where(
            m.SparePart.status.in_([m.PART_DELAYED, m.PART_SHORTAGE])
        )
    ).all()
    occupancies = db.scalars(
        select(m.DockOccupancy)
        .options(selectinload(m.DockOccupancy.dock), selectinload(m.DockOccupancy.project))
        .where(m.DockOccupancy.status != m.OCCUPANCY_RELEASED)
        .order_by(m.DockOccupancy.start_date)
    ).all()

    return {
        "project_total": count(m.Project),
        "project_active": count(m.Project, m.Project.status == m.PROJECT_IN_PROGRESS),
        "task_total": count(m.Task),
        "task_blocked": len(blocked),
        "part_delayed": len([p for p in delayed_parts if p.status == m.PART_DELAYED]),
        "part_shortage": len([p for p in delayed_parts if p.status == m.PART_SHORTAGE]),
        "dock_total": count(m.Dock),
        "blocked_tasks": [
            {"id": t.id, "code": t.code, "name": t.name, "reason": t.affected_reason}
            for t in blocked
        ],
        "occupancies": [
            {
                "id": o.id,
                "dock_code": o.dock.code if o.dock else None,
                "project_code": o.project.code if o.project else None,
                "ship_name": o.project.ship_name if o.project else None,
                "start_date": o.start_date,
                "end_date": o.end_date,
                "status": o.status,
            }
            for o in occupancies
        ],
    }


# ===========================================================================
# 坞位
# ===========================================================================

dock_router = APIRouter(prefix="/api/docks", tags=["docks"])


@dock_router.get("", response_model=list[s.Dock])
def list_docks(db: Session = Depends(get_db)):
    return db.scalars(select(m.Dock).order_by(m.Dock.code)).all()


@dock_router.post("", response_model=s.Dock, status_code=201)
def create_dock(payload: s.DockCreate, db: Session = Depends(get_db)):
    dock = m.Dock(**payload.model_dump())
    db.add(dock)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "坞位编号已存在")
    return dock


# ===========================================================================
# 施工队
# ===========================================================================

team_router = APIRouter(prefix="/api/teams", tags=["teams"])


@team_router.get("", response_model=list[s.WorkTeam])
def list_teams(db: Session = Depends(get_db)):
    return db.scalars(select(m.WorkTeam).order_by(m.WorkTeam.code)).all()


@team_router.post("", response_model=s.WorkTeam, status_code=201)
def create_team(payload: s.WorkTeamCreate, db: Session = Depends(get_db)):
    team = m.WorkTeam(**payload.model_dump())
    db.add(team)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "施工队编号已存在")
    return team


@team_router.get("/{team_id}/schedule")
def team_schedule(team_id: int, db: Session = Depends(get_db)):
    """某施工队的排班（含任务/项目信息），用于检测同队时间冲突。"""
    rows = db.scalars(
        select(m.TeamAssignment)
        .options(
            selectinload(m.TeamAssignment.task),
            selectinload(m.TeamAssignment.team),
        )
        .where(m.TeamAssignment.team_id == team_id)
        .order_by(m.TeamAssignment.planned_start)
    ).all()
    return [
        {
            "id": a.id,
            "team_id": a.team_id,
            "team_name": a.team.name,
            "task_id": a.task_id,
            "task_code": a.task.code,
            "task_name": a.task.name,
            "project_id": a.task.project_id,
            "planned_start": a.planned_start,
            "planned_end": a.planned_end,
            "status": a.status,
        }
        for a in rows
    ]


# ===========================================================================
# 项目
# ===========================================================================

@router.get("/projects", response_model=list[s.Project], tags=["projects"])
def list_projects(db: Session = Depends(get_db)):
    return db.scalars(
        select(m.Project)
        .options(selectinload(m.Project.dock))
        .order_by(m.Project.planned_start)
    ).all()


@router.post("/projects", response_model=s.ProjectDetail, status_code=201, tags=["projects"])
def create_project(payload: s.ProjectCreate, db: Session = Depends(get_db)):
    if payload.dock_id is not None and db.get(m.Dock, payload.dock_id) is None:
        raise HTTPException(400, "指定的坞位不存在")
    project = m.Project(
        **payload.model_dump(),
        baseline_end=None,
        planned_end=payload.planned_start,
    )
    db.add(project)
    db.flush()
    if project.dock_id is not None:
        db.add(
            m.DockOccupancy(
                dock_id=project.dock_id,
                project_id=project.id,
                start_date=project.planned_start,
                end_date=project.planned_start,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "项目编号已存在")
    return _load_project_graph(db, project.id)


@router.get("/projects/{project_id}", response_model=s.ProjectDetail, tags=["projects"])
def get_project(project_id: int, db: Session = Depends(get_db)):
    return _load_project_graph(db, project_id)


@router.put("/projects/{project_id}", response_model=s.ProjectDetail, tags=["projects"])
def update_project(project_id: int, payload: s.ProjectUpdate, db: Session = Depends(get_db)):
    project = _get_project(db, project_id)
    data = payload.model_dump(exclude_unset=True)
    if "dock_id" in data and data["dock_id"] is not None and db.get(m.Dock, data["dock_id"]) is None:
        raise HTTPException(400, "指定的坞位不存在")
    for k, v in data.items():
        setattr(project, k, v)
    if data.get("status") == m.PROJECT_COMPLETED and project.planned_end:
        project.actual_end = project.planned_end
    db.commit()
    return _load_project_graph(db, project_id)


@router.delete("/projects/{project_id}", status_code=204, tags=["projects"])
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = _get_project(db, project_id)
    db.delete(project)
    db.commit()


# ------------------------- 任务 -------------------------

@router.get("/projects/{project_id}/tasks", response_model=list[s.Task], tags=["tasks"])
def list_tasks(project_id: int, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    tasks = db.scalars(
        select(m.Task)
        .options(
            selectinload(m.Task.depends_on),
            selectinload(m.Task.assignments).selectinload(m.TeamAssignment.team),
            selectinload(m.Task.parts),
        )
        .where(m.Task.project_id == project_id)
        .order_by(m.Task.sort_order, m.Task.planned_start)
    ).all()
    return tasks


@router.post(
    "/projects/{project_id}/tasks",
    response_model=s.Task,
    status_code=201,
    tags=["tasks"],
)
def create_task(project_id: int, payload: s.TaskCreate, db: Session = Depends(get_db)):
    project = _load_project_graph(db, project_id)
    end = payload.planned_start + timedelta(days=payload.duration_days - 1)

    dep_tasks: list[m.Task] = []
    for dep_id in payload.depends_on:
        dep = db.get(m.Task, dep_id)
        if dep is None or dep.project_id != project_id:
            raise HTTPException(400, f"前置任务 {dep_id} 不存在")
        dep_tasks.append(dep)

    teams: list[m.WorkTeam] = []
    for team_id in payload.team_ids:
        team = db.get(m.WorkTeam, team_id)
        if team is None:
            raise HTTPException(400, f"施工队 {team_id} 不存在")
        teams.append(team)

    task = m.Task(
        project_id=project_id,
        code=payload.code,
        name=payload.name,
        phase=payload.phase,
        planned_start=payload.planned_start,
        planned_end=end,
        baseline_start=payload.planned_start,
        baseline_end=end,
        duration_days=payload.duration_days,
        needs_dock=payload.needs_dock,
        sort_order=payload.sort_order,
        depends_on=dep_tasks,
    )
    db.add(task)
    db.flush()
    for team in teams:
        db.add(
            m.TeamAssignment(
                task_id=task.id,
                team_id=team.id,
                planned_start=task.planned_start,
                planned_end=task.planned_end,
            )
        )
    db.flush()
    recalculate_project(db, project)
    db.commit()
    return _load_task_graph(db, task.id)


def _load_task_graph(db: Session, task_id: int) -> m.Task:
    stmt = (
        select(m.Task)
        .where(m.Task.id == task_id)
        .options(
            selectinload(m.Task.depends_on),
            selectinload(m.Task.assignments).selectinload(m.TeamAssignment.team),
            selectinload(m.Task.parts),
        )
    )
    task = db.scalar(stmt)
    if task is None:
        raise HTTPException(404, "任务不存在")
    return task


@router.put("/projects/{project_id}/tasks/{task_id}", response_model=s.Task, tags=["tasks"])
def update_task(
    project_id: int, task_id: int, payload: s.TaskUpdate, db: Session = Depends(get_db)
):
    task = _get_task(db, project_id, task_id)
    data = payload.model_dump(exclude_unset=True)

    # 手工修改开工日 / 工期属于重新排基线
    new_start = data.pop("planned_start", None)
    new_duration = data.pop("duration_days", None)
    if new_start is not None:
        task.baseline_start = new_start
        task.planned_start = new_start
    duration = new_duration if new_duration is not None else task.duration_days
    if new_duration is not None:
        task.duration_days = new_duration
    start = task.baseline_start
    task.baseline_end = start + timedelta(days=duration - 1)

    for k, v in data.items():
        setattr(task, k, v)
    if data.get("status") == m.TASK_IN_PROGRESS and task.actual_start is None:
        task.actual_start = task.planned_start
    if data.get("status") == m.TASK_DONE:
        task.progress = 100
        task.actual_end = data.get("actual_end") or task.planned_end

    db.flush()
    project = _load_project_graph(db, project_id)
    recalculate_project(db, project)
    db.commit()
    return _load_task_graph(db, task_id)


@router.delete(
    "/projects/{project_id}/tasks/{task_id}", status_code=204, tags=["tasks"]
)
def delete_task(project_id: int, task_id: int, db: Session = Depends(get_db)):
    task = _get_task(db, project_id, task_id)
    db.delete(task)
    db.flush()
    project = _load_project_graph(db, project_id)
    recalculate_project(db, project)
    db.commit()


@router.post(
    "/projects/{project_id}/tasks/{task_id}/dependencies",
    response_model=s.Task,
    tags=["tasks"],
)
def add_dependency(
    project_id: int, task_id: int, payload: s.DependencyCreate, db: Session = Depends(get_db)
):
    task = _get_task(db, project_id, task_id)
    dep = db.get(m.Task, payload.depends_on_id)
    if dep is None or dep.project_id != project_id:
        raise HTTPException(400, "前置任务不存在")
    if dep.id == task_id:
        raise HTTPException(400, "任务不能依赖自身")
    if dep not in task.depends_on:
        task.depends_on.append(dep)
        db.flush()
        project = _load_project_graph(db, project_id)
        recalculate_project(db, project)
        db.commit()
    return _load_task_graph(db, task_id)


# ------------------------- 施工队排班 -------------------------

@router.post(
    "/projects/{project_id}/tasks/{task_id}/assignments",
    response_model=s.Assignment,
    status_code=201,
    tags=["assignments"],
)
def assign_team(
    project_id: int, task_id: int, payload: s.AssignmentCreate, db: Session = Depends(get_db)
):
    task = _get_task(db, project_id, task_id)
    team = db.get(m.WorkTeam, payload.team_id)
    if team is None:
        raise HTTPException(400, "施工队不存在")
    if any(a.team_id == team.id for a in task.assignments):
        raise HTTPException(409, "该施工队已分配到此任务")
    assignment = m.TeamAssignment(
        task_id=task.id,
        team_id=team.id,
        planned_start=task.planned_start,
        planned_end=task.planned_end,
    )
    db.add(assignment)
    db.commit()
    return db.scalar(
        select(m.TeamAssignment)
        .options(selectinload(m.TeamAssignment.team))
        .where(m.TeamAssignment.id == assignment.id)
    )


@router.delete(
    "/projects/{project_id}/tasks/{task_id}/assignments/{assignment_id}",
    status_code=204,
    tags=["assignments"],
)
def unassign_team(
    project_id: int, task_id: int, assignment_id: int, db: Session = Depends(get_db)
):
    _get_task(db, project_id, task_id)
    assignment = db.get(m.TeamAssignment, assignment_id)
    if assignment is None or assignment.task_id != task_id:
        raise HTTPException(404, "排班不存在")
    db.delete(assignment)
    db.commit()


# ------------------------- 备件 -------------------------

@router.get(
    "/projects/{project_id}/parts",
    response_model=list[s.SparePart],
    tags=["parts"],
)
def list_parts(project_id: int, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    return db.scalars(
        select(m.SparePart)
        .where(m.SparePart.project_id == project_id)
        .order_by(m.SparePart.required_date)
    ).all()


@router.post(
    "/projects/{project_id}/parts",
    response_model=s.SparePart,
    status_code=201,
    tags=["parts"],
)
def create_part(project_id: int, payload: s.SparePartCreate, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    if payload.task_id is not None:
        task = db.get(m.Task, payload.task_id)
        if task is None or task.project_id != project_id:
            raise HTTPException(400, "备件关联的任务不存在")
    part = m.SparePart(project_id=project_id, **payload.model_dump())
    db.add(part)
    db.flush()
    project = _load_project_graph(db, project_id)
    recalculate_project(db, project)
    db.commit()
    return part


@router.put("/parts/{part_id}", response_model=s.SparePart, tags=["parts"])
def update_part(part_id: int, payload: s.SparePartUpdate, db: Session = Depends(get_db)):
    part = db.get(m.SparePart, part_id)
    if part is None:
        raise HTTPException(404, "备件不存在")
    data = payload.model_dump(exclude_unset=True)
    if data.get("task_id") is not None:
        task = db.get(m.Task, data["task_id"])
        if task is None or task.project_id != part.project_id:
            raise HTTPException(400, "备件关联的任务不存在")
    for k, v in data.items():
        setattr(part, k, v)
    if data.get("status") == m.PART_ARRIVED and part.arrived_date is None:
        part.arrived_date = part.eta
    db.flush()
    project = _load_project_graph(db, part.project_id)
    recalculate_project(db, project)
    db.commit()
    return part


# ------------------------- 坞位占用 -------------------------

@router.get(
    "/projects/{project_id}/occupancies",
    response_model=list[s.Occupancy],
    tags=["occupancies"],
)
def list_occupancies(project_id: int, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    return db.scalars(
        select(m.DockOccupancy)
        .options(selectinload(m.DockOccupancy.dock))
        .where(m.DockOccupancy.project_id == project_id)
    ).all()


@router.post(
    "/projects/{project_id}/occupancies",
    response_model=s.Occupancy,
    status_code=201,
    tags=["occupancies"],
)
def create_occupancy(
    project_id: int, payload: s.OccupancyCreate, db: Session = Depends(get_db)
):
    project = _get_project(db, project_id)
    if db.get(m.Dock, payload.dock_id) is None:
        raise HTTPException(400, "坞位不存在")
    if payload.end_date < payload.start_date:
        raise HTTPException(400, "结束日期不能早于开始日期")

    overlap = db.scalars(
        select(m.DockOccupancy).where(
            m.DockOccupancy.dock_id == payload.dock_id,
            m.DockOccupancy.status != m.OCCUPANCY_RELEASED,
            m.DockOccupancy.project_id != project_id,
        )
    ).all()
    for o in overlap:
        if o.start_date <= payload.end_date and payload.start_date <= o.end_date:
            raise HTTPException(
                409,
                f"坞位档期与项目 {o.project_id} 占用期重叠"
                f"（{o.start_date} ~ {o.end_date}）",
            )

    occupancy = m.DockOccupancy(project_id=project_id, **payload.model_dump())
    db.add(occupancy)
    project.dock_id = payload.dock_id
    db.commit()
    return db.scalar(
        select(m.DockOccupancy)
        .options(selectinload(m.DockOccupancy.dock))
        .where(m.DockOccupancy.id == occupancy.id)
    )


@router.post(
    "/projects/{project_id}/recalc", response_model=s.RecalcResult, tags=["schedule"]
)
def recalc(project_id: int, db: Session = Depends(get_db)):
    project = _load_project_graph(db, project_id)
    result = recalculate_project(db, project)
    db.commit()
    return s.RecalcResult(
        project_id=project_id,
        planned_end=result["planned_end"],
        delay_days=result["delay_days"],
        blocked_tasks=result["blocked"],
        shifted_tasks=result["shifted"],
    )


@router.get(
    "/projects/{project_id}/conflicts",
    response_model=list[s.ConflictReport],
    tags=["schedule"],
)
def conflicts(project_id: int, db: Session = Depends(get_db)):
    _get_project(db, project_id)
    return find_dock_conflicts(db, project_id)
