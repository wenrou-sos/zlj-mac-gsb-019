from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Column,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base

# ---------------------------------------------------------------------------
# Association tables
# ---------------------------------------------------------------------------

# Work items are split into a WBS of sub-tasks. A task may depend on other
# tasks finishing first (finish-to-start relationship).
task_dependencies = Table(
    "task_dependencies",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("depends_on_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
)

# A task can be assigned to several construction teams (施工队).
task_teams = Table(
    "task_teams",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("team_id", Integer, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
)


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class Project(Base):
    """A ship repair project occupying a dock period (坞期)."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    ship_name = Column(String(200), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(20), default="planned")  # planned/in_progress/completed/delayed
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    """A single repair work item (维修子项) produced by project splitting."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    progress = Column(Integer, default=0)  # 0-100 (%)
    status = Column(String(20), default="pending")
    # pending / in_progress / blocked / done

    # JSON-ish text kept portable between PostgreSQL and SQLite.
    # Keys: "parts", "team", "dock" -> human readable blocking reason.
    blockers = Column(Text, default="")

    project = relationship("Project", back_populates="tasks")

    dependencies = relationship(
        "Task",
        secondary=task_dependencies,
        primaryjoin="Task.id==task_dependencies.c.task_id",
        secondaryjoin="Task.id==task_dependencies.c.depends_on_id",
        backref="dependents",
    )
    teams = relationship("Team", secondary=task_teams, back_populates="tasks")
    parts = relationship("Part", back_populates="task", cascade="all, delete-orphan")
    bookings = relationship("DockBooking", back_populates="task", cascade="all, delete-orphan")


class Team(Base):
    """A construction team (施工队) that can be rostered onto tasks."""

    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    specialty = Column(String(100), default="")  # e.g. 船体 / 机电 / 涂装
    size = Column(Integer, default=1)

    tasks = relationship("Task", secondary=task_teams, back_populates="teams")


class Part(Base):
    """Spare part (备件) required by a task, with arrival tracking."""

    __tablename__ = "parts"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    quantity = Column(Integer, default=1)
    eta = Column(Date, nullable=True)  # estimated time of arrival
    arrived = Column(Boolean, default=False)
    arrived_at = Column(Date, nullable=True)

    task = relationship("Task", back_populates="parts")


class Dock(Base):
    """A dry dock / berth (坞位) whose occupancy is scheduled."""

    __tablename__ = "docks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    capacity = Column(String(100), default="")  # e.g. 10万吨级

    bookings = relationship("DockBooking", back_populates="dock", cascade="all, delete-orphan")


class DockBooking(Base):
    """Occupancy interval of a dock by a task.

    Per-dock overlapping bookings are treated as conflicts.
    """

    __tablename__ = "dock_bookings"

    id = Column(Integer, primary_key=True, index=True)
    dock_id = Column(Integer, ForeignKey("docks.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    dock = relationship("Dock", back_populates="bookings")
    task = relationship("Task", back_populates="bookings")


class ActivityLog(Base):
    """Audit trail, in particular automatic schedule adjustments."""

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    kind = Column(String(30), default="info")  # info/warning/adjustment
    message = Column(Text, nullable=False)
