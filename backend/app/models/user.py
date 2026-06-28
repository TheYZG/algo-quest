"""
用户模型 - SQLAlchemy ORM
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 金币系统
    coins: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    # 刷题统计
    total_solved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    easy_solved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    medium_solved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hard_solved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 冒险模式进度
    adventure_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
