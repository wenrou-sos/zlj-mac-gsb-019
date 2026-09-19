import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def _resolve_database_url() -> str:
    # 测试环境优先使用环境变量中的 URL（pytest 会注入 SQLite）
    url = os.getenv("SHIPYARD_DATABASE_URL") or settings.database_url
    # 兼容 postgres:// 这种写法
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url


DATABASE_URL = _resolve_database_url()
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """开发/演示环境用：按模型直接建表（生产应走 Alembic 迁移）。"""
    # 确保所有模型都已注册到 metadata
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
