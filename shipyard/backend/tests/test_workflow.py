"""端到端业务测试：覆盖四大模块 + 延期/缺件自动传播。"""
from datetime import date, timedelta

from app.models import models as m


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_full_workflow(client):
    today = date(2026, 9, 19)

    # ---- 1. 基础资源：坞位 + 施工队 ----
    r = client.post("/api/docks", json={"code": "DT", "name": "测试干坞", "length_m": 200, "width_m": 35})
    assert r.status_code == 201, r.text
    dock_id = r.json()["id"]

    r = client.post("/api/teams", json={"code": "TE", "name": "测试轮机队", "specialty": "轮机"})
    assert r.status_code == 201, r.text
    team_id = r.json()["id"]

    # ---- 2. 建项目 ----
    r = client.post(
        "/api/projects",
        json={
            "code": "TEST-001",
            "name": "测试轮坞修",
            "ship_name": "测试轮",
            "planned_start": today.isoformat(),
            "dock_id": dock_id,
        },
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    # 建项目时应自动生成坞位占用
    assert len(r.json()["occupancies"]) == 1

    # ---- 3. WBS 任务拆分：T1 -> T2 -> T3 ----
    def make_task(code, name, offset, duration, deps=None, teams=None):
        r = client.post(
            f"/api/projects/{pid}/tasks",
            json={
                "code": code,
                "name": name,
                "phase": "轮机",
                "planned_start": (today + timedelta(days=offset)).isoformat(),
                "duration_days": duration,
                "depends_on": deps or [],
                "team_ids": teams or [],
                "needs_dock": True,
            },
        )
        assert r.status_code == 201, r.text
        return r.json()

    t1 = make_task("TT1", "拆尾轴", 0, 2, teams=[team_id])
    t2 = make_task("TT2", "换轴承", 2, 3, deps=[t1["id"]], teams=[team_id])
    t3 = make_task("TT3", "轴系校中", 5, 2, deps=[t2["id"]])

    # 初始无备件问题：三任务都不是 blocked
    assert t1["status"] != "blocked"
    assert t2["status"] != "blocked"

    # ---- 4. T2 需要的轴承“缺件”（无 ETA）→ T2 阻断，T3 级联阻断 ----
    r = client.post(
        f"/api/projects/{pid}/parts",
        json={
            "code": "BEARING-1",
            "name": "中间轴承",
            "quantity": 1,
            "required_date": t2["planned_start"],
            "eta": None,
            "status": "shortage",
            "task_id": t2["id"],
        },
    )
    assert r.status_code == 201, r.text

    r = client.get(f"/api/projects/{pid}")
    tasks = {t["code"]: t for t in r.json()["tasks"]}
    assert tasks["TT2"]["status"] == "blocked"
    assert "缺件" in (tasks["TT2"]["affected_reason"] or "")
    # 下游 T3 因前置受阻同样 blocked
    assert tasks["TT3"]["status"] == "blocked"
    assert "前置任务 TT2" in (tasks["TT3"]["affected_reason"] or "")

    # 仪表盘应感知阻断
    dash = client.get("/api/dashboard").json()
    assert dash["task_blocked"] >= 2
    assert dash["part_shortage"] >= 1

    # ---- 5. 缺件解决：备件到货 → 阻断解除 ----
    parts = client.get(f"/api/projects/{pid}/parts").json()
    bearing = next(p for p in parts if p["code"] == "BEARING-1")
    r = client.put(f"/api/parts/{bearing['id']}", json={"status": "arrived", "arrived_date": today.isoformat()})
    assert r.status_code == 200, r.text

    tasks = {t["code"]: t for t in client.get(f"/api/projects/{pid}").json()["tasks"]}
    assert tasks["TT2"]["status"] != "blocked"
    assert tasks["TT3"]["status"] != "blocked"

    # ---- 6. 备件延期 4 天到货 → T2/T3 顺排并记录延期 ----
    eta = date.fromisoformat(t2["planned_start"]) + timedelta(days=4)
    r = client.put(
        f"/api/parts/{bearing['id']}",
        json={"status": "delayed", "arrived_date": None, "eta": eta.isoformat()},
    )
    assert r.status_code == 200, r.text

    tasks = {t["code"]: t for t in client.get(f"/api/projects/{pid}").json()["tasks"]}
    assert tasks["TT2"]["status"] != "blocked"  # 有 ETA 不算缺件
    assert tasks["TT2"]["planned_start"] == eta.isoformat()
    assert tasks["TT2"]["delay_days"] >= 4
    assert tasks["TT3"]["delay_days"] >= 3  # 延期沿依赖链传导
    project = client.get(f"/api/projects/{pid}").json()
    assert project["delay_days"] >= 4

    # 施工队排班日期随任务联动
    assignment = next(a for a in tasks["TT1"]["assignments"] if a["team_id"] == team_id)
    assert assignment["planned_start"] == tasks["TT1"]["planned_start"]

    # ---- 7. 坞位冲突检测：另一项目同坞档期重叠应 409 ----
    r = client.post(
        "/api/projects",
        json={
            "code": "TEST-002",
            "name": "另一艘船",
            "ship_name": "邻船",
            "planned_start": today.isoformat(),
        },
    )
    pid2 = r.json()["id"]
    r = client.post(
        f"/api/projects/{pid2}/occupancies",
        json={
            "dock_id": dock_id,
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=10)).isoformat(),
        },
    )
    assert r.status_code == 409

    # ---- 8. 任务完工后作为锚点，不被重排改动 ----
    r = client.put(f"/api/projects/{pid}/tasks/{t1['id']}", json={"status": "done"})
    assert r.status_code == 200
    done = r.json()
    assert done["actual_end"] == done["planned_end"]

    # ---- 9. 手工重排接口可调用 ----
    r = client.post(f"/api/projects/{pid}/recalc")
    assert r.status_code == 200
    assert "blocked_tasks" in r.json()
