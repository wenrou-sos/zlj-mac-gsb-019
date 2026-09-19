from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectBase(BaseModel):
    name: str
    ship_name: str
    start_date: date
    end_date: date
    status: str = "planned"
    notes: str = ""

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    ship_name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class Project(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    tasks: list["Task"] = []


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


class TaskBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    progress: int = 0
    status: str = "pending"

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v


class TaskCreate(TaskBase):
    project_id: int
    depends_on: list[int] = []
    team_ids: list[int] = []


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    progress: Optional[int] = None
    status: Optional[str] = None
    depends_on: Optional[list[int]] = None
    team_ids: Optional[list[int]] = None


class TaskDelay(BaseModel):
    """Body for POST /tasks/{id}/delay - report a delay of N days."""

    days: int


class TaskBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_date: date
    end_date: date
    status: str


class Task(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    blockers: str = ""
    depends_on: list[int] = []
    team_ids: list[int] = []
    parts: list["Part"] = []
    bookings: list["Booking"] = []


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------


class TeamBase(BaseModel):
    name: str
    specialty: str = ""
    size: int = 1


class TeamCreate(TeamBase):
    pass


class Team(TeamBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_ids: list[int] = []


# ---------------------------------------------------------------------------
# Part
# ---------------------------------------------------------------------------


class PartBase(BaseModel):
    name: str
    quantity: int = 1
    eta: Optional[date] = None
    arrived: bool = False


class PartCreate(PartBase):
    task_id: int


class PartUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[int] = None
    eta: Optional[date] = None
    arrived: Optional[bool] = None


class Part(PartBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    arrived_at: Optional[date] = None


# ---------------------------------------------------------------------------
# Dock
# ---------------------------------------------------------------------------


class DockBase(BaseModel):
    name: str
    capacity: str = ""


class DockCreate(DockBase):
    pass


class Dock(DockBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class BookingBase(BaseModel):
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v


class BookingCreate(BookingBase):
    dock_id: int
    task_id: int
    # When the dock is busy, automatically move to the next free slot and
    # cascade the change. False -> return HTTP 409 instead.
    auto_adjust: bool = True


class Booking(BookingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dock_id: int
    task_id: int


# ---------------------------------------------------------------------------
# Logs / dashboard
# ---------------------------------------------------------------------------


class ActivityLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    kind: str
    message: str


class DashboardOut(BaseModel):
    project_count: int
    task_count: int
    blocked_task_count: int
    delayed_part_count: int
    dock_count: int
    team_count: int
    booking_conflict_count: int


# Resolve forward references (Task <-> Part/Booking, Project -> Task).
Project.model_rebuild()
Task.model_rebuild()
