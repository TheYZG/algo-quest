"""
Assistant 对话记录模型
"""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    problem_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # user, assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    help_level: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # hint, guide, explain, chat
    coins_spent: Mapped[int] = mapped_column(default=0, nullable=False)
    context_snapshot: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # 记录当时的题目上下文 JSON
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
