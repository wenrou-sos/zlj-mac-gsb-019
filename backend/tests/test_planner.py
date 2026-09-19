"""Tests for the automatic replanning engine (延期/缺件/冲突)."""


def _blockers(task: dict) -> dict:
    import json

    return json.loads(task["blockers"] or "{}")


# ---------------------------------------------------------------------------
# Delay cascading
# ---------------------------------------------------------------------------


def test_delay_cascades_through_dependencies(client, factory):
    project = factory.project(days=12)
    t1 = factory.task(project["id"], "甲", "2026-09-01", "2026-09-05")
    t2 = factory.task(
        project["id"], "乙", "2026-09-06", "2026-09-10", depends_on=[t1["id"]]
    )
    t3 = factory.task(
        project["id"], "丙", "2026-09-11", "2026-09-15", depends_on=[t2["id"]]
    )

    resp = client.post(f"/api/tasks/{t1['id']}/delay", json={"days": 3})
    assert resp.status_code == 200
    data = resp.json()
    # All three tasks in the chain are reported as affected.
    assert data["count"] == 3
    affected = {t["id"]: t for t in data["affected_tasks"]}
    assert affected[t1["id"]]["start_date"] == "2026-09-04"
    assert affected[t1["id"]]["end_date"] == "2026-09-08"
    assert affected[t2["id"]]["start_date"] == "2026-09-08"
    assert affected[t3["id"]]["start_date"] == "2026-09-12"

    # Dock period (坞期) of the project is extended automatically past the
    # last task (now ending 2026-09-16).
    updated = client.get(f"/api/projects/{project['id']}").json()
    assert updated["end_date"] == "2026-09-16"


def test_delay_zero_rejected(client, factory):
    project = factory.project()
    t = factory.task(project["id"], "甲")
    resp = client.post(f"/api/tasks/{t['id']}/delay", json={"days": 0})
    assert resp.status_code == 400


def test_delay_does_not_move_completed_successors(client, factory):
    project = factory.project(days=60)
    t1 = factory.task(project["id"], "甲", "2026-09-01", "2026-09-05")
    t2 = factory.task(
        project["id"],
        "乙",
        "2026-09-06",
        "2026-09-10",
        depends_on=[t1["id"]],
        status="done",
        progress=100,
    )
    resp = client.post(f"/api/tasks/{t1['id']}/delay", json={"days": 10})
    assert resp.status_code == 200
    affected_ids = {t["id"] for t in resp.json()["affected_tasks"]}
    assert t2["id"] not in affected_ids


# ---------------------------------------------------------------------------
# Missing parts
# ---------------------------------------------------------------------------


def test_missing_part_blocks_task(client, factory):
    project = factory.project()
    t = factory.task(project["id"], "螺旋桨更换", "2026-09-01", "2026-09-05")
    factory.part(t["id"], "新螺旋桨", eta="2026-09-10")

    detail = client.get(f"/api/tasks/{t['id']}").json()
    assert detail["status"] == "blocked"
    assert "缺件" in _blockers(detail)["parts"]
    # Task is auto-pushed to the part arrival day.
    assert detail["start_date"] == "2026-09-10"


def test_part_eta_postponed_replans(client, factory):
    project = factory.project(days=60)
    t1 = factory.task(project["id"], "甲", "2026-09-01", "2026-09-05")
    t2 = factory.task(
        project["id"], "乙", "2026-09-06", "2026-09-10", depends_on=[t1["id"]]
    )
    part = factory.part(t1["id"], "主轴", eta="2026-09-03")

    # ETA slips to the 20th -> task 甲 moves to the 20th, 乙 cascades.
    resp = client.patch(f"/api/parts/{part['id']}", json={"eta": "2026-09-20"})
    assert resp.status_code == 200
    affected = {t["id"]: t for t in resp.json()["affected_tasks"]}
    assert t1["id"] in affected and t2["id"] in affected

    detail = client.get(f"/api/tasks/{t1['id']}").json()
    assert detail["start_date"] == "2026-09-20"

    # Downstream task is marked as affected while waiting on the blocked one.
    downstream = client.get(f"/api/tasks/{t2['id']}").json()
    assert "upstream" in _blockers(downstream)
    assert downstream["status"] == "blocked"


def test_part_arrival_unblocks_task(client, factory):
    project = factory.project()
    t = factory.task(project["id"], "涂装", "2026-09-01", "2026-09-05")
    part = factory.part(t["id"], "涂料", eta="2026-09-10")
    assert client.get(f"/api/tasks/{t['id']}").json()["status"] == "blocked"

    resp = client.patch(f"/api/parts/{part['id']}", json={"arrived": True})
    assert resp.status_code == 200
    detail = client.get(f"/api/tasks/{t['id']}").json()
    assert "parts" not in _blockers(detail)
    assert detail["status"] != "blocked"


def test_part_without_eta_is_blocked(client, factory):
    project = factory.project()
    t = factory.task(project["id"], " mysterious", "2026-09-01", "2026-09-05")
    factory.part(t["id"], "待定货件", eta=None)
    detail = client.get(f"/api/tasks/{t['id']}").json()
    assert detail["status"] == "blocked"
    assert "到货日期未定" in _blockers(detail)["parts"]


# ---------------------------------------------------------------------------
# Team rostering conflicts
# ---------------------------------------------------------------------------


def test_team_double_booking_marks_both_tasks(client, factory):
    project = factory.project(days=40)
    t1 = factory.task(project["id"], "甲", "2026-09-01", "2026-09-10")
    t2 = factory.task(project["id"], "乙", "2026-09-05", "2026-09-15")
    team = factory.team("机电班")

    r1 = client.post(
        f"/api/teams/assign?task_id={t1['id']}&team_id={team['id']}"
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/api/teams/assign?task_id={t2['id']}&team_id={team['id']}"
    )
    assert r2.status_code == 200

    for tid in (t1["id"], t2["id"]):
        detail = client.get(f"/api/tasks/{tid}").json()
        assert "team" in _blockers(detail)
        assert detail["status"] == "blocked"


def test_non_overlapping_team_assignments_ok(client, factory):
    project = factory.project(days=40)
    t1 = factory.task(project["id"], "甲", "2026-09-01", "2026-09-05")
    t2 = factory.task(project["id"], "乙", "2026-09-10", "2026-09-15")
    team = factory.team()
    client.post(f"/api/teams/assign?task_id={t1['id']}&team_id={team['id']}")
    client.post(f"/api/teams/assign?task_id={t2['id']}&team_id={team['id']}")
    for tid in (t1["id"], t2["id"]):
        detail = client.get(f"/api/tasks/{tid}").json()
        assert "team" not in _blockers(detail)


# ---------------------------------------------------------------------------
# Dock occupancy
# ---------------------------------------------------------------------------


def test_dock_booking_auto_reschedules(client, factory):
    project = factory.project(days=60)
    t1 = factory.task(project["id"], "甲船工程", "2026-09-01", "2026-09-10")
    t2 = factory.task(project["id"], "乙船工程", "2026-09-05", "2026-09-15")
    dock = factory.dock("1号干坞")

    r1 = client.post(
        "/api/docks/bookings",
        json={
            "dock_id": dock["id"],
            "task_id": t1["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-10",
        },
    )
    assert r1.status_code == 201

    r2 = client.post(
        "/api/docks/bookings",
        json={
            "dock_id": dock["id"],
            "task_id": t2["id"],
            "start_date": "2026-09-05",
            "end_date": "2026-09-12",
        },
    )
    assert r2.status_code == 201
    data = r2.json()
    assert data["moved"] is True
    # Booking lands immediately after the first one (duration is 7 days).
    assert data["booking"]["start_date"] == "2026-09-11"
    assert data["booking"]["end_date"] == "2026-09-18"
    # Task itself is shifted to wait for the dock.
    assert {t["id"] for t in data["affected_tasks"]} == {t2["id"]}


def test_dock_booking_conflict_without_auto_adjust(client, factory):
    project = factory.project(days=40)
    t1 = factory.task(project["id"], "甲", "2026-09-01", "2026-09-10")
    t2 = factory.task(project["id"], "乙", "2026-09-05", "2026-09-15")
    dock = factory.dock()
    client.post(
        "/api/docks/bookings",
        json={
            "dock_id": dock["id"],
            "task_id": t1["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-10",
        },
    )
    resp = client.post(
        "/api/docks/bookings",
        json={
            "dock_id": dock["id"],
            "task_id": t2["id"],
            "start_date": "2026-09-05",
            "end_date": "2026-09-12",
            "auto_adjust": False,
        },
    )
    assert resp.status_code == 409
    assert "坞位" in resp.json()["detail"]


def test_different_docks_do_not_conflict(client, factory):
    project = factory.project(days=40)
    t1 = factory.task(project["id"], "甲", "2026-09-01", "2026-09-10")
    dock_a = factory.dock("1号坞")
    dock_b = factory.dock("2号坞")
    for dock in (dock_a, dock_b):
        resp = client.post(
            "/api/docks/bookings",
            json={
                "dock_id": dock["id"],
                "task_id": t1["id"],
                "start_date": "2026-09-01",
                "end_date": "2026-09-10",
            },
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Dashboard & logs
# ---------------------------------------------------------------------------


def test_dashboard_counts_blockers(client, factory):
    project = factory.project()
    t = factory.task(project["id"], "甲", "2026-09-01", "2026-09-05")
    factory.part(t["id"], "缺的货", eta="2026-09-20")
    data = client.get("/api/dashboard").json()
    assert data["project_count"] == 1
    assert data["task_count"] == 1
    assert data["blocked_task_count"] == 1
    assert data["delayed_part_count"] == 1


def test_adjustments_are_logged(client, factory):
    project = factory.project(days=60)
    t = factory.task(project["id"], "甲", "2026-09-01", "2026-09-05")
    client.post(f"/api/tasks/{t['id']}/delay", json={"days": 4})
    logs = client.get("/api/logs").json()
    messages = [l["message"] for l in logs]
    assert any("顺延 4 天" in m for m in messages)
    assert any(l["kind"] == "adjustment" for l in logs)
