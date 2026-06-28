"""
题目数据模型 - SQLite 主存储
存储题目完整数据：描述、代码模板、解答、统计等
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Float, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Problem(Base):
    """题目表 — 所有题目数据的完整 SQL 存储"""
    __tablename__ = "problems"

    # 主键：4位题号字符串（如 "0001", "2503"）
    id: Mapped[str] = mapped_column(String(10), primary_key=True)

    # 题号（整数，方便排序和比较）
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)

    # 标题
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    title_cn: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    # URL slug（如 "two-sum", "add-two-numbers"）
    slug: Mapped[str] = mapped_column(String(200), nullable=False, default="", index=True)

    # 难度：Easy / Medium / Hard
    difficulty: Mapped[str] = mapped_column(String(10), index=True, nullable=False, default="Medium")

    # 标签（JSON 数组字符串，如 '["数组","哈希表"]'）
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # 算法王国归属（主王国，兼容旧逻辑）
    kingdom: Mapped[str] = mapped_column(String(50), index=True, nullable=False, default="混沌领域")
    kingdom_emoji: Mapped[str] = mapped_column(String(10), nullable=False, default="🌪️")

    # 所有归属王国（JSON 数组，如 '["数据结构工坊","数学高塔","混沌领域"]'）
    kingdoms: Mapped[str] = mapped_column(Text, nullable=False, default='["混沌领域"]')

    # 题目描述（HTML/Markdown）
    description_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_cn_html: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # 提示（JSON 数组字符串）
    hints: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # 解答代码（JSON 对象字符串，语言 → 代码）
    solutions: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    # 统计信息
    likes: Mapped[int] = mapped_column(Integer, default=0)
    dislikes: Mapped[int] = mapped_column(Integer, default=0)
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    submissions_count: Mapped[int] = mapped_column(Integer, default=1)

    # AC 率（辅助计算字段）
    ac_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self):
        return f"<Problem #{self.number} {self.title_cn}>"
