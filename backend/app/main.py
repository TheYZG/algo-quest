"""
FastAPI 应用入口
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import init_db
from app.models import User, Submission, AssistantMessage, Problem  # noqa: F401 - 确保模型被加载

settings = get_settings()

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# API 路由
from app.api import auth, problems, assistant, progress, admin

app.include_router(auth.router)
app.include_router(problems.router)
app.include_router(assistant.router)
app.include_router(progress.router)
app.include_router(admin.router)


# ============================================================
# 前端页面服务
# ============================================================
@app.get("/")
async def serve_index():
    """主页面"""
    html_path = os.path.join(PROJECT_ROOT, "quest-mode.html")
    return FileResponse(html_path, media_type="text/html; charset=utf-8")


@app.get("/search-demo")
async def serve_search_demo():
    """AI 搜索演示页"""
    html_path = os.path.join(PROJECT_ROOT, "ai-search-demo.html")
    return FileResponse(html_path, media_type="text/html; charset=utf-8")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
