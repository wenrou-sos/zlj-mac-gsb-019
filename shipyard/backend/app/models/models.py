from datetime import date

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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# ---------------------------------------------------------------------------
# 枚举常量（字符串枚举，跨 SQLite / PostgreSQL 通用）
# ---------------------------------------------------------------------------

PROJECT_PLANNED = "planned"
PROJECT_IN_PROGRESS = "in_progress"
PROJECT_COMPLETED = "completed"

TASK_PENDING = "pending"          # 未开始
TASK_IN_PROGRESS = "in_progress"  # 进行中
TASK_BLOCKED = "blocked"          # 受阻（缺件 / 前置延期）
TASK_DONE = "done"                # 完工

PART_PENDING = "pending"          # 待采购/未发运
PART_IN_TRANSIT = "in_transit"    # 运输中
PART_DELAYED = "delayed"          # 到货延期
PART_SHORTAGE = "shortage"        # 缺件（无法供货）
PART_ARRIVED = "arrived"          # 已到货

OCCUPANCY_RESERVED = "reserved"   # 已预约
OCCUPANCY_OCCUPIED = "occupied"   # 占用中
OCCUPANCY_RELEASED = "released"   # 已释放

ASSIGNMENT_SCHEDULED = "scheduled"
ASSIGNMENT_WORKING = "working"
ASSIGNMENT_RELEASED = "released"

# 任务 ↔ 前置依赖（多对多，完成-开始）
task_dependencies = Table(
    "task_dependencies",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("depends_on_id", Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("task_id", "depends_on_id", name="uq_task_dependency"),
)


class Dock(Base):
    """干船坞 / 浮船坞 坞位"""

    __tablename__ = "docks"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    length_m: Mapped[float] = mapped_column(Float, default=0)   # 可容纳船长
    width_m: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(16), default="available")  # available / maintenance

    occupancies: Mapped[list["DockOccupancy"]] = relationship(
        back_populates="dock", cascade="all, delete-orphan"
    )


class Project(Base):
    """船舶维修项目（一条船一次进坞）"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    ship_name: Mapped[str] = mapped_column(String(128))
    imo: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=PROJECT_PLANNED)
    planned_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_end: Mapped[date | None] = mapped_column(Date, nullable=True)       # 排程后
    baseline_end: Mapped[date | None] = mapped_column(Date, nullable=True)      # 原始计划
    actual_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    dock_id: Mapped[int | None] = mapped_column(ForeignKey("docks.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    delay_days: Mapped[int] = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())

    dock: Mapped["Dock | None"] = relationship()
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    parts: Mapped[list["SparePart"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    occupancies: Mapped[list["DockOccupancy"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Task(Base):
    """WBS 拆分后的维修任务"""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(128))
    phase: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 坞修阶段：进坞/除锈/机电...
    status: Mapped[str] = mapped_column(String(16), default=TASK_PENDING)
    progress: Mapped[int] = mapped_column(Integer, default=0)

    # 排程结果
    planned_start: Mapped[date] = mapped_column(Date)
    planned_end: Mapped[date] = mapped_column(Date)
    # 基线计划（用于计算延期天数，不随重排改动）
    baseline_start: Mapped[date] = mapped_column(Date)
    baseline_end: Mapped[date] = mapped_column(Date)
    actual_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    duration_days: Mapped[int] = mapped_column(Integer, default=1)
    delay_days: Mapped[int] = mapped_column(Integer, default=0)
    affected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_dock: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped["Project"] = relationship(back_populates="tasks")
    depends_on: Mapped[list["Task"]] = relationship(
        secondary=task_dependencies,
        primaryjoin="Task.id == task_dependencies.c.task_id",
        secondaryjoin="Task.id == task_dependencies.c.depends_on_id",
        backref="dependents",
    )
    assignments: Mapped[list["TeamAssignment"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    parts: Mapped[list["SparePart"]] = relationship(back_populates="task")


class WorkTeam(Base):
    """施工队"""

    __tablename__ = "work_teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    specialty: Mapped[str] = mapped_column(String(64))  # 轮机/船体/电气/涂装
    leader: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    size: Mapped[int] = mapped_column(Integer, default=5)

    assignments: Mapped[list["TeamAssignment"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class TeamAssignment(Base):
    """施工队 × 任务 排班"""

    __tablename__ = "team_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("work_teams.id", ondelete="CASCADE"), index=True)
    planned_start: Mapped[date] = mapped_column(Date)
    planned_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default=ASSIGNMENT_SCHEDULED)

    task: Mapped["Task"] = relationship(back_populates="assignments")
    team: Mapped["WorkTeam"] = relationship(back_populates="assignments")


class SparePart(Base):
    """备件及其到货跟踪（挂到需求任务上）"""

    __tablename__ = "spare_parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(128))
    supplier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    required_date: Mapped[date] = mapped_column(Date)   # 任务要求到货日
    eta: Mapped[date | None] = mapped_column(Date, nullable=True)  # 预计到货
    arrived_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=PART_PENDING)

    project: Mapped["Project"] = relationship(back_populates="parts")
    task: Mapped["Task | None"] = relationship(back_populates="parts")


class DockOccupancy(Base):
    """坞位占用档期"""

    __tablename__ = "dock_occupancies"

    id: Mapped[int] = mapped_column(primary_key=True)
    dock_id: Mapped[int] = mapped_column(ForeignKey("docks.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default=OCCUPANCY_RESERVED)

    dock: Mapped["Dock"] = relationship(back_populates="occupancies")
    project: Mapped["Project"] = relationship(back_populates="occupancies")
