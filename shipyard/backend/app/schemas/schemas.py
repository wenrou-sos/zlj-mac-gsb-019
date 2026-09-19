from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- Dock ----------------

class DockBase(BaseModel):
    code: str
    name: str
    length_m: float = 0
    width_m: float = 0
    status: str = "available"


class DockCreate(DockBase):
    pass


class Dock(DockBase, ORMModel):
    id: int


# ---------------- WorkTeam ----------------

class WorkTeamBase(BaseModel):
    code: str
    name: str
    specialty: str
    leader: str | None = None
    phone: str | None = None
    size: int = 5


class WorkTeamCreate(WorkTeamBase):
    pass


class WorkTeam(WorkTeamBase, ORMModel):
    id: int


# ---------------- SparePart ----------------

class SparePartBase(BaseModel):
    code: str
    name: str
    supplier: str | None = None
    quantity: int = 1
    required_date: date
    eta: date | None = None
    status: str = "pending"
    task_id: int | None = None


class SparePartCreate(SparePartBase):
    pass


class SparePartUpdate(BaseModel):
    eta: date | None = None
    arrived_date: date | None = None
    status: str | None = None
    supplier: str | None = None
    quantity: int | None = None
    task_id: int | None = None


class SparePart(SparePartBase, ORMModel):
    id: int
    project_id: int


# ---------------- Assignments / Tasks ----------------

class AssignmentBase(BaseModel):
    team_id: int


class AssignmentCreate(AssignmentBase):
    pass


class Assignment(ORMModel):
    id: int
    task_id: int
    team_id: int
    planned_start: date
    planned_end: date
    status: str
    team: WorkTeam | None = None


class DependencyCreate(BaseModel):
    depends_on_id: int


class TaskBase(BaseModel):
    code: str
    name: str
    phase: str | None = None
    planned_start: date
    duration_days: int = Field(default=1, ge=1)
    needs_dock: bool = False
    sort_order: int = 0


class TaskCreate(TaskBase):
    depends_on: list[int] = []
    team_ids: list[int] = []


class TaskUpdate(BaseModel):
    name: str | None = None
    phase: str | None = None
    status: str | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    planned_start: date | None = None
    duration_days: int | None = Field(default=None, ge=1)
    needs_dock: bool | None = None
    actual_start: date | None = None
    actual_end: date | None = None


class Task(ORMModel):
    id: int
    project_id: int
    code: str
    name: str
    phase: str | None
    status: str
    progress: int
    planned_start: date
    planned_end: date
    baseline_start: date
    baseline_end: date
    actual_start: date | None
    actual_end: date | None
    duration_days: int
    delay_days: int
    affected_reason: str | None
    needs_dock: bool
    sort_order: int
    depends_on: list["Task"] = []
    assignments: list[Assignment] = []
    parts: list[SparePart] = []


# ---------------- Project ----------------

class ProjectBase(BaseModel):
    code: str
    name: str
    ship_name: str
    imo: str | None = None
    planned_start: date
    dock_id: int | None = None
    description: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    dock_id: int | None = None
    planned_start: date | None = None
    description: str | None = None


class Project(ProjectBase, ORMModel):
    id: int
    status: str
    planned_end: date | None
    baseline_end: date | None
    actual_end: date | None
    delay_days: int
    dock: Dock | None = None
    tasks: list[Task] = []
    parts: list[SparePart] = []


class ProjectDetail(Project):
    occupancies: list["Occupancy"] = []


# ---------------- Occupancy ----------------

class OccupancyCreate(BaseModel):
    dock_id: int
    start_date: date
    end_date: date


class Occupancy(ORMModel):
    id: int
    dock_id: int
    project_id: int
    start_date: date
    end_date: date
    status: str
    dock: Dock | None = None


# ---------------- 计划重算结果 ----------------

class RecalcResult(BaseModel):
    project_id: int
    planned_end: date
    delay_days: int
    blocked_tasks: list[int]
    shifted_tasks: list[int]


class ConflictReport(BaseModel):
    occupancy_id: int
    dock_id: int
    other_project_id: int
    start_date: date
    end_date: date
