import os
import tempfile

# 必须在 import 应用代码之前指定测试库（SQLite 内存文件，无需 PostgreSQL）
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["SHIPYARD_DATABASE_URL"] = f"sqlite:///{_tmp.name}"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.database import Base, engine
from app.main import app


@pytest.fixture(scope="session")
def client():
    # SQLite 开启外键约束，贴近 PostgreSQL 行为
    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
