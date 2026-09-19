import os

import pytest

# Use an in-memory SQLite database for the whole test suite.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    # Each test starts with an empty schema.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


def make_project(client, name="测试坞修", days=30, **overrides):
    from datetime import date, timedelta

    payload = {
        "name": name,
        "ship_name": "测试船",
        "start_date": date(2026, 9, 1).isoformat(),
        "end_date": (date(2026, 9, 1) + timedelta(days=days)).isoformat(),
    }
    payload.update(overrides)
    resp = client.post("/api/projects", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_task(client, project_id, name, start="2026-09-01", end="2026-09-05", **extra):
    payload = {
        "project_id": project_id,
        "name": name,
        "start_date": start,
        "end_date": end,
    }
    payload.update(extra)
    resp = client.post("/api/tasks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def factory(client):
    class Factory:
        project = staticmethod(lambda **kw: make_project(client, **kw))
        task = staticmethod(lambda *a, **kw: make_task(client, *a, **kw))

        @staticmethod
        def team(name="船体一班", specialty="船体"):
            resp = client.post(
                "/api/teams", json={"name": name, "specialty": specialty, "size": 5}
            )
            assert resp.status_code == 201, resp.text
            return resp.json()

        @staticmethod
        def dock(name="1号坞"):
            resp = client.post("/api/docks", json={"name": name, "capacity": "5万吨"})
            assert resp.status_code == 201, resp.text
            return resp.json()

        @staticmethod
        def part(task_id, name="备件", eta=None, arrived=False):
            payload = {"task_id": task_id, "name": name, "quantity": 1}
            if eta:
                payload["eta"] = eta
            payload["arrived"] = arrived
            resp = client.post("/api/parts", json=payload)
            assert resp.status_code == 201, resp.text
            return resp.json()

    return Factory()
