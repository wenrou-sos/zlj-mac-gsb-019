import logging
import os
from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import dock_router, router, team_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine, init_db
from app.models import models as m

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shipyard")

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(dock_router)
app.include_router(team_router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "app": settings.app_name}


@app.on_event("startup")
def on_startup():
    init_db()
    if os.getenv("SHIPYARD_SEED_DEMO", "1") == "1":
        _seed_demo_data()


def _seed_demo_data() -> None:
    """空库时灌入一份可直接演示的坞修项目数据。"""
    db = SessionLocal()
    try:
        if db.query(m.Project).count() > 0:
            return

        d1 = m.Dock(code="D1", name="一号干船坞", length_m=250, width_m=40)
        d2 = m.Dock(code="D2", name="二号浮船坞", length_m=180, width_m=28)
        db.add_all([d1, d2])

        t1 = m.WorkTeam(code="HULL", name="船体一班", specialty="船体", leader="王大勇", size=12)
        t2 = m.WorkTeam(code="ENG", name="轮机二班", specialty="轮机", leader="李建国", size=10)
        t3 = m.WorkTeam(code="PAINT", name="涂装三班", specialty="涂装", leader="赵海燕", size=8)
        db.add_all([t1, t2, t3])
        db.flush()

        start = date.today()
        project = m.Project(
            code="P-2026-009",
            name="远洋之星轮坞修",
            ship_name="远洋之星",
            imo="IMO-9472801",
            status=m.PROJECT_IN_PROGRESS,
            planned_start=start,
            baseline_end=start + timedelta(days=19),
            planned_end=start + timedelta(days=19),
            dock_id=d1.id,
            description="五年特检：船体测厚、舵桨检修、涂装、轴系更换",
        )
        db.add(project)
        db.flush()
        db.add(
            m.DockOccupancy(
                dock_id=d1.id,
                project_id=project.id,
                start_date=start,
                end_date=start + timedelta(days=19),
                status=m.OCCUPANCY_OCCUPIED,
            )
        )

        def task(code, name, phase, offset, duration, deps=(), teams=(), need_dock=True):
            s = start + timedelta(days=offset)
            e = s + timedelta(days=duration - 1)
            t = m.Task(
                project_id=project.id,
                code=code,
                name=name,
                phase=phase,
                planned_start=s,
                planned_end=e,
                baseline_start=s,
                baseline_end=e,
                duration_days=duration,
                needs_dock=need_dock,
                sort_order=offset,
                depends_on=list(deps),
            )
            db.add(t)
            db.flush()
            for team in teams:
                db.add(
                    m.TeamAssignment(
                        task_id=t.id,
                        team_id=team.id,
                        planned_start=s,
                        planned_end=e,
                    )
                )
            return t

        tk1 = task("T1", "进坞坐墩", "进坞", 0, 1, teams=[t1])
        tk2 = task("T2", "船体清砂除锈", "船体", 1, 4, deps=[tk1], teams=[t1])
        tk3 = task("T3", "船体测厚换板", "船体", 5, 4, deps=[tk2], teams=[t1])
        tk4 = task("T4", "尾轴及螺旋桨拆装", "轮机", 3, 5, deps=[tk1], teams=[t2])
        tk5 = task("T5", "主机轴系校中", "轮机", 8, 3, deps=[tk4], teams=[t2])
        tk6 = task("T6", "全船涂装", "涂装", 9, 5, deps=[tk3], teams=[t3])
        tk7 = task("T7", "出坞试航", "完工", 18, 1, deps=[tk5, tk6], teams=[t1, t2])
        db.flush()

        # 一个会延期的备件 + 一个缺件，演示自动标记
        db.add(
            m.SparePart(
                project_id=project.id,
                task_id=tk5.id,
                code="SP-SHAFT-01",
                name="中间轴承",
                supplier="沪东重机",
                quantity=2,
                required_date=tk5.baseline_start,
                eta=tk5.baseline_start + timedelta(days=3),
                status=m.PART_DELAYED,
            )
        )
        db.add(
            m.SparePart(
                project_id=project.id,
                task_id=tk4.id,
                code="SP-SEAL-07",
                name="尾轴密封组件",
                supplier="进口待询价",
                quantity=1,
                required_date=tk4.baseline_start,
                eta=None,
                status=m.PART_SHORTAGE,
            )
        )
        db.flush()

        from app.services.scheduling import recalculate_project

        recalculate_project(db, project)
        db.commit()
        logger.info("演示数据已初始化：项目 P-2026-009")
    finally:
        db.close()
