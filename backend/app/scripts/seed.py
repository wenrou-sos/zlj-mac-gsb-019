"""Seed a realistic demo dataset.

Idempotent: only seeds when the database contains no projects.
Run with:  python -m app.scripts.seed
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from .. import models, planner


def seed(db: Session) -> bool:
    if db.query(models.Project).count() > 0:
        return False

    d0 = date.today()

    # --- project -----------------------------------------------------------
    project = models.Project(
        name="远洋号 坞修工程",
        ship_name="远洋号",
        start_date=d0,
        end_date=d0 + timedelta(days=40),
        status="in_progress",
        notes="五年特检 + 螺旋桨更换 + 压载舱涂装",
    )
    db.add(project)
    db.flush()

    # --- work breakdown (维修项目拆分) --------------------------------------
    t1 = models.Task(
        project_id=project.id,
        name="进坞与船体测厚",
        start_date=d0,
        end_date=d0 + timedelta(days=4),
        status="in_progress",
        progress=60,
    )
    t2 = models.Task(
        project_id=project.id,
        name="螺旋桨拆装更换",
        start_date=d0 + timedelta(days=5),
        end_date=d0 + timedelta(days=12),
    )
    t3 = models.Task(
        project_id=project.id,
        name="压载舱喷砂涂装",
        start_date=d0 + timedelta(days=13),
        end_date=d0 + timedelta(days=25),
    )
    t4 = models.Task(
        project_id=project.id,
        name="轴系校中与码头试航",
        start_date=d0 + timedelta(days=26),
        end_date=d0 + timedelta(days=35),
    )
    db.add_all([t1, t2, t3, t4])
    db.flush()

    # finish-to-start chain
    t2.dependencies = [t1]
    t3.dependencies = [t2]
    t4.dependencies = [t3]

    # --- teams (施工队) -----------------------------------------------------
    hull = models.Team(name="船体一班", specialty="船体/测厚", size=12)
    mech = models.Team(name="机电二班", specialty="轴系/螺旋桨", size=8)
    paint = models.Team(name="涂装三班", specialty="喷砂/涂装", size=15)
    db.add_all([hull, mech, paint])
    db.flush()
    t1.teams = [hull]
    t2.teams = [mech]
    t3.teams = [paint]
    t4.teams = [mech]

    # --- spare parts (备件) -------------------------------------------------
    db.add_all(
        [
            models.Part(
                task_id=t2.id,
                name="新螺旋桨",
                quantity=1,
                eta=d0 + timedelta(days=8),  # after planned start -> blocked
            ),
            models.Part(
                task_id=t2.id,
                name="尾轴密封件",
                quantity=4,
                eta=d0 + timedelta(days=3),
            ),
            models.Part(
                task_id=t3.id,
                name="环氧涂料",
                quantity=200,
                eta=d0 + timedelta(days=10),
            ),
            models.Part(
                task_id=t1.id,
                name="测厚探头",
                quantity=2,
                eta=d0 - timedelta(days=1),
                arrived=True,
                arrived_at=d0 - timedelta(days=1),
            ),
        ]
    )

    # --- docks (坞位) -------------------------------------------------------
    dock1 = models.Dock(name="1号干船坞", capacity="10万吨级")
    dock2 = models.Dock(name="2号干船坞", capacity="5万吨级")
    db.add_all([dock1, dock2])
    db.flush()
    db.add(
        models.DockBooking(
            dock_id=dock1.id,
            task_id=t1.id,
            start_date=d0,
            end_date=d0 + timedelta(days=20),
        )
    )

    # Run the same event path as the API so a fresh demo shows a fully
    # adjusted schedule (shifted dates + adjustment logs).
    for part in db.query(models.Part).filter(models.Part.arrived.is_(False)).all():
        planner.part_changed(db, part)
    db.commit()
    return True


def main() -> None:
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        created = seed(db)
        print("已写入演示数据" if created else "数据库已有数据, 跳过")
    finally:
        db.close()


if __name__ == "__main__":
    main()
