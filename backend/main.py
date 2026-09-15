"""应用入口：创建 FastAPI 应用、注册路由并提供前端页面。"""

from __future__ import annotations

import base64
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from backend import __version__
from backend.database import SessionLocal, init_db
from backend.routers import achievements, departments, persons, reports, rules
from backend.seed import seed_all

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with_demo = os.getenv("SEED_DEMO", "1") not in {"0", "false", "False"}
    db = SessionLocal()
    try:
        seed_all(db, with_demo=with_demo)
    finally:
        db.close()
    yield


app = FastAPI(
    title="职称评审科研成果认定与积分计算系统",
    description="科研成果录入与认定、积分规则配置、自动积分计算、统计报表与导出。",
    version=__version__,
    lifespan=lifespan,
)


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    """设置 APP_PASSWORD 后启用 HTTP Basic 登录保护（公网部署建议开启）。"""
    password = os.getenv("APP_PASSWORD")
    if not password or request.url.path == "/health":
        return await call_next(request)

    username = os.getenv("APP_USERNAME", "admin")
    header = request.headers.get("authorization", "")
    if header.startswith("Basic "):
        try:
            decoded = base64.b64decode(header[6:]).decode("utf-8")
            user, _, pwd = decoded.partition(":")
            if secrets.compare_digest(user, username) and secrets.compare_digest(pwd, password):
                return await call_next(request)
        except Exception:  # noqa: BLE001
            pass

    return Response(
        status_code=401,
        content="需要登录",
        headers={"WWW-Authenticate": 'Basic realm="Title Review System"'},
    )


app.include_router(departments.router)
app.include_router(persons.router)
app.include_router(rules.router)
app.include_router(achievements.router)
app.include_router(reports.router)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/health", tags=["系统"], summary="健康检查")
def health() -> dict:
    return {"status": "ok", "version": __version__}
