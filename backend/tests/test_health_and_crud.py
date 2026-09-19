"""Smoke tests: the application starts and basic CRUD works."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_openapi_available(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "/api/projects" in resp.json()["paths"]


def test_dashboard_empty(client):
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_count"] == 0
    assert data["task_count"] == 0


def test_project_crud(client, factory):
    project = factory.project()
    assert project["ship_name"] == "测试船"
    assert project["status"] == "planned"

    listed = client.get("/api/projects").json()
    assert len(listed) == 1 and listed[0]["id"] == project["id"]

    resp = client.patch(
        f"/api/projects/{project['id']}", json={"status": "in_progress"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_invalid_date_range_rejected(client):
    resp = client.post(
        "/api/projects",
        json={
            "name": "bad",
            "ship_name": "船",
            "start_date": "2026-09-10",
            "end_date": "2026-09-01",
        },
    )
    assert resp.status_code == 422


def test_task_splitting_with_dependencies(client, factory):
    project = factory.project()
    t1 = factory.task(project["id"], "进坞测厚")
    t2 = factory.task(
        project["id"],
        "螺旋桨更换",
        start="2026-09-06",
        end="2026-09-12",
        depends_on=[t1["id"]],
    )
    assert t2["depends_on"] == [t1["id"]]

    detail = client.get(f"/api/projects/{project['id']}").json()
    names = [t["name"] for t in detail["tasks"]]
    assert names == ["进坞测厚", "螺旋桨更换"]


def test_self_dependency_rejected(client, factory):
    project = factory.project()
    t = factory.task(project["id"], "任务甲")
    resp = client.patch(f"/api/tasks/{t['id']}", json={"depends_on": [t["id"]]})
    assert resp.status_code == 400
