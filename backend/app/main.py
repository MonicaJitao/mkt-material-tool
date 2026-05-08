"""
FastAPI 应用入口。

启动命令（在 backend/ 目录下）：
  uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
"""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

# ── 路由注册 ──────────────────────────────────────────────────────────────────

from app.api.routes_templates import router as templates_router
from app.api.routes_projects import router as projects_router
from app.api.routes_campaigns import router as campaigns_router

app.include_router(templates_router)
app.include_router(projects_router)
app.include_router(campaigns_router)

from app.api.routes_generation import router as generation_router
from app.api.routes_assets import router as assets_router

app.include_router(generation_router)
app.include_router(assets_router)

from app.api.routes_html import campaigns_router as html_campaigns_router
from app.api.routes_html import html_router

app.include_router(html_campaigns_router)
app.include_router(html_router)

# 将 workspace 目录挂载为静态文件，供 HTML 海报引用底图
# 确保目录存在后再挂载（测试环境 init_db 尚未运行时目录可能不存在）
_workspace_abs = os.path.abspath(settings.WORKSPACE_DIR)
os.makedirs(_workspace_abs, exist_ok=True)
app.mount(
    "/workspace",
    StaticFiles(directory=_workspace_abs),
    name="workspace",
)


@app.get("/health")
def health():
    return {"ok": True, "service": settings.APP_NAME}
