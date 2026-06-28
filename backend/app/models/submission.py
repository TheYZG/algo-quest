"""
做题记录模型
"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    problem_id: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    problem_title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, accepted, wrong_answer, runtime_error, timeout
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str | None] = mapped_column(String(10000), nullable=True)
    result: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    coins_earned: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
