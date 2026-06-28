"""
数据库连接 - SQLAlchemy async + SQLite
使用 WAL 模式提升并发写入性能
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

# 使用可配置的绝对路径，避免跨平台歧义
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(_base_dir, settings.DATABASE_PATH)
os.makedirs(os.path.dirname(db_path), exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={
        "check_same_thread": False,
        "timeout": 15,  # 写入超时等待
    },
)

async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


# 导入所有模型以注册到 Base.metadata（必须在 init_db 之前）
from app.models.user import User  # noqa: E402, F401
from app.models.submission import Submission  # noqa: E402, F401
from app.models.assistant import AssistantMessage  # noqa: E402, F401
from app.models.problem import Problem  # noqa: E402, F401


async def get_db() -> AsyncSession:
    """获取数据库会话（FastAPI 依赖注入）"""
    async with async_session() as session:
        yield session


async def init_db():
    """初始化数据库：创建所有表 + 启用 WAL 模式"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # WAL 模式：提升并发读取性能，允许同时读写
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        # 启用外键约束
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
