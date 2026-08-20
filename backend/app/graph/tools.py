"""
专家 Agent 工具层 — LangChain @tool 函数
工具自行开启数据库会话（无 FastAPI DI），供 ReAct Agent 调用
"""
import asyncio
import json
import logging

from langchain_core.tools import tool
from sqlalchemy import select, func, and_

from app.database import async_session
from app.models.problem import Problem
from app.models.submission import Submission
from app.services.search import semantic_search

logger = logging.getLogger(__name__)


# ============================================================
# 题目类工具（Tutor / Judge / Reviewer）
# ============================================================

@tool
async def get_problem_detail(problem_id: str) -> str:
    """获取题目详情（标题、难度、标签、题面描述）。problem_id 为 4 位题号，如 "0001"。"""
    from app.services.problems import get_problem_detail as _detail

    async with async_session() as db:
        problem = await _detail(db, problem_id)
    if not problem:
        return json.dumps({"error": f"题目 {problem_id} 不存在"}, ensure_ascii=False)
    return json.dumps({
        "id": problem.id,
        "title_cn": problem.title_cn,
        "difficulty": problem.difficulty,
        "tags": problem.tags,
        "description_cn": problem.description_cn_html[:1500],
        "hints": problem.hints[:3],
    }, ensure_ascii=False)


@tool
async def get_reference_solution(problem_id: str, language: str = "python") -> str:
    """获取题目的参考题解代码。language 可选 python/cpp/java/javascript/go。"""
    from app.services.problems import get_problem_detail as _detail

    async with async_session() as db:
        problem = await _detail(db, problem_id)
    if not problem:
        return json.dumps({"error": f"题目 {problem_id} 不存在"}, ensure_ascii=False)
    solutions = problem.solutions or {}
    code = (
        solutions.get(language)
        or solutions.get("python")
        or solutions.get("cpp")
        or solutions.get("java")
        or ""
    )
    return json.dumps({
        "problem_id": problem_id,
        "language": language,
        "reference_code": code[:4000],
    }, ensure_ascii=False)


# ============================================================
# 检索类工具（Scout / Planner）
# ============================================================

@tool
async def semantic_search_problems(query: str, top_k: int = 5) -> str:
    """用自然语言语义搜索题库，如 query="类似背包问题的动态规划入门题"。返回最匹配的题目列表。"""
    def _sync_search():
        return semantic_search(query, top_k=top_k)

    results = await asyncio.to_thread(_sync_search)
    if not results:
        return json.dumps({"results": [], "note": "没有找到相关题目"}, ensure_ascii=False)
    return json.dumps({
        "results": [
            {
                "id": r.problem.id,
                "title_cn": r.problem.title_cn,
                "difficulty": r.problem.difficulty,
                "tags": r.problem.tags[:4],
                "kingdom": r.problem.kingdom,
                "relevance": r.relevance,
            }
            for r in results
        ]
    }, ensure_ascii=False)


@tool
async def get_user_progress(user_id: str, problem_id: str = "") -> str:
    """查询用户做题进度。可传 problem_id 查当前题的尝试历史，不传则查总体统计。"""
    async with async_session() as db:
        total = await db.scalar(
            select(func.count()).select_from(Submission).where(
                Submission.user_id == user_id)
        )
        accepted = await db.scalar(
            select(func.count()).select_from(Submission).where(and_(
                Submission.user_id == user_id,
                Submission.status == "accepted",
            ))
        )
        data = {
            "total_submissions": total or 0,
            "accepted": accepted or 0,
        }
        if problem_id:
            rows = (await db.execute(
                select(Submission.status).where(and_(
                    Submission.user_id == user_id,
                    Submission.problem_id == problem_id,
                )).order_by(Submission.created_at)
            )).scalars().all()
            data["current_problem"] = {
                "problem_id": problem_id,
                "attempts": len(rows),
                "wa_count": sum(1 for s in rows if s == "wrong_answer"),
                "last_status": rows[-1] if rows else None,
            }
    return json.dumps(data, ensure_ascii=False)


# ============================================================
# 规划类工具（Planner）
# ============================================================

async def get_weak_kingdoms(user_id: str, top_n: int = 3) -> dict:
    """聚合用户未通过的王国（内部函数，@tool 包装在下方）"""
    async with async_session() as db:
        rows = (await db.execute(
            select(Problem.kingdoms, func.count())
            .join(Submission, Submission.problem_id == Problem.id)
            .where(and_(
                Submission.user_id == user_id,
                Submission.status != "accepted",
            ))
            .group_by(Problem.kingdoms)
        )).all()

    kingdom_fails: dict[str, int] = {}
    for kingdoms_json, cnt in rows:
        try:
            entries = json.loads(kingdoms_json or "[]")
        except Exception:
            continue
        for entry in entries:
            name = entry[0] if isinstance(entry, list) and entry else entry
            if isinstance(name, str):
                kingdom_fails[name] = kingdom_fails.get(name, 0) + cnt

    ranked = sorted(
        [{"kingdom": k, "failed_attempts": v} for k, v in kingdom_fails.items()],
        key=lambda x: x["failed_attempts"], reverse=True,
    )[:top_n]
    return {"kingdoms": ranked}


@tool
async def get_weak_kingdoms_tool(user_id: str, top_n: int = 3) -> str:
    """分析用户的薄弱算法王国（按未通过次数排序），供学习规划使用。"""
    return json.dumps(await get_weak_kingdoms(user_id, top_n), ensure_ascii=False)
