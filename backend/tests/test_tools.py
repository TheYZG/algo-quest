"""工具层测试：weak_kingdoms 聚合逻辑（注入内存 SQLite session 工厂）"""
import json

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.graph import tools as gt


class _Base(DeclarativeBase):
    pass


@pytest.fixture
async def session_factory():
    """内存数据库 + 最小表结构（复刻 Problem/Submission 关键列）"""
    from sqlalchemy import Column, String, Integer, Text

    class Problem(_Base):
        __tablename__ = "problems"
        id = Column(String(20), primary_key=True)
        kingdoms = Column(Text, nullable=True)

    class Submission(_Base):
        __tablename__ = "submissions"
        id = Column(String(36), primary_key=True)
        user_id = Column(String(36))
        problem_id = Column(String(20))
        status = Column(String(20))

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        db.add_all([
            Problem(id="0001", kingdoms=json.dumps([["动态规划圣殿", "🏛️"]])),
            Problem(id="0002", kingdoms=json.dumps([["字符串神殿", "🔤"]])),
            Submission(id="s1", user_id="u1", problem_id="0001", status="wrong_answer"),
            Submission(id="s2", user_id="u1", problem_id="0001", status="wrong_answer"),
            Submission(id="s3", user_id="u1", problem_id="0002", status="accepted"),
        ])
        await db.commit()

    yield factory
    await engine.dispose()


async def test_weak_kingdoms聚合未通过次数(session_factory, monkeypatch):
    monkeypatch.setattr(gt, "async_session", session_factory)
    result = await gt.get_weak_kingdoms(user_id="u1", top_n=3)
    # 动态规划圣殿 2 次未通过，应排第一；字符串神殿已 AC 不计入
    assert result["kingdoms"][0]["kingdom"] == "动态规划圣殿"
    assert result["kingdoms"][0]["failed_attempts"] == 2
