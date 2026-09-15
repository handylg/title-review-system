"""数据库连接与会话管理。

本地默认使用 SQLite；在云平台上可通过环境变量 DATABASE_URL 指定
PostgreSQL 等数据库（Render 的 Postgres 连接串可直接使用）。
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "review.db"


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        return f"sqlite:///{DB_PATH.as_posix()}"
    # 兼容裸 postgres:// 前缀，并统一使用 psycopg (v3) 驱动
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = _database_url()

_is_sqlite = DATABASE_URL.startswith("sqlite")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    """FastAPI 依赖：提供数据库会话。"""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """创建所有数据表。"""
    from backend import models  # noqa: F401  确保模型已注册

    models.Base.metadata.create_all(bind=engine)
