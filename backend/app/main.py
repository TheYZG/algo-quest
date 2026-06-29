"""
FastAPI 应用入口
"""
import os
import sys
import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import init_db
from app.models import User, Submission, AssistantMessage, Problem  # noqa: F401 - 确保模型被加载

settings = get_settings()

# ============================================================
# 日志系统配置
# ============================================================
LOG_LEVEL = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d | %(message)s"
LOG_DATE_FORMAT = "%m-%d %H:%M:%S"

logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
# 抑制第三方库的冗余日志
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"应用启动: {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"日志级别: {settings.LOG_LEVEL.upper()}")
    await init_db()
    logger.info(f"数据库初始化完成: {settings.DATABASE_PATH}")
    yield
    logger.info("应用关闭")


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


# ============================================================
# 请求日志中间件
# ============================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    logger.info(
        "%s %s → %d (%.0fms)",
        request.method, request.url.path, response.status_code, elapsed * 1000,
    )
    return response


# ============================================================
# 全局异常处理
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理的异常，返回统一结构"""
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部错误",
            "error": str(exc) if settings.DEBUG else "请稍后重试",
            "path": request.url.path,
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """处理参数校验错误"""
    logger.warning("参数错误: %s → %s", request.url.path, exc)
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "path": request.url.path},
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
