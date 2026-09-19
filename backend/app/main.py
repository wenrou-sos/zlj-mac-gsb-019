"""FastAPI application entry point for the ship repair dock management API."""

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, SessionLocal, engine

# Import models so that metadata is populated before create_all().
from . import models  # noqa: F401
from .routers import dashboard, docks, parts, projects, tasks, teams

logger = logging.getLogger("shipyard")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _wait_for_database(max_attempts: int = 30) -> None:
    """Wait for PostgreSQL to accept connections (Docker startup ordering)."""
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return
        except Exception as exc:  # pragma: no cover - depends on environment
            logger.warning("等待数据库就绪 (%s/%s): %s", attempt, max_attempts, exc)
            time.sleep(1)
    raise RuntimeError("数据库连接失败, 请检查配置")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _wait_for_database()
    Base.metadata.create_all(bind=engine)
    if os.getenv("SEED_ON_STARTUP", "false").lower() == "1":
        _seed_if_empty()
    yield


def _seed_if_empty() -> None:
    from .scripts.seed import seed

    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


app = FastAPI(
    title="船舶维修坞期管理平台 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(teams.router)
app.include_router(parts.router)
app.include_router(docks.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "service": "shipyard-dock-manager"}


# Serve the built Vue frontend when it has been copied into the image.
if STATIC_DIR.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=STATIC_DIR / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api/") or full_path == "health":
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        from fastapi.responses import FileResponse

        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"detail": "frontend not built"}, status_code=404)
