"""
数据管理 API - 题目导入、统计
导入操作使用后台任务，避免阻塞事件循环
"""
import asyncio
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.problem import Problem
from app.services.importer import import_problems
from app.vectordb import get_collection_stats

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["管理"])

# 导入任务状态追踪
_import_status = {"running": False, "stats": None}


@router.post("/import")
async def trigger_import(background_tasks: BackgroundTasks):
    """
    触发题目数据导入（后台异步执行）

    首次调用立即返回，导入在后台进行。
    可通过 GET /api/admin/import-status 查看进度。
    """
    if _import_status["running"]:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": "导入已在进行中，请等待完成",
            },
        )

    # 在后台线程池中执行（避免阻塞事件循环）
    def run_import():
        _import_status["running"] = True
        _import_status["stats"] = None
        try:
            stats = import_problems()
            _import_status["stats"] = stats
        except Exception as e:
            logger.error("导入失败: %s", e)
            _import_status["stats"] = {"error": str(e)}
        finally:
            _import_status["running"] = False

    background_tasks.add_task(asyncio.to_thread, run_import)

    return {
        "success": True,
        "message": "导入已在后台启动，请稍后查询状态",
    }


@router.get("/import-status")
async def import_status():
    """查询导入进度"""
    return _import_status


@router.get("/chroma-stats")
async def chroma_stats():
    """查看 ChromaDB 状态"""
    stats = get_collection_stats()
    return stats


@router.get("/db-stats")
async def db_stats(db: AsyncSession = Depends(get_db)):
    """查看 SQLite 数据库统计"""
    # 题目总数
    total_result = await db.execute(select(func.count(Problem.id)))
    total = total_result.scalar() or 0

    # 按难度分布
    diff_result = await db.execute(
        select(Problem.difficulty, func.count(Problem.id))
        .group_by(Problem.difficulty)
    )
    by_difficulty = {row[0]: row[1] for row in diff_result.all()}

    # 按王国分布
    kingdom_result = await db.execute(
        select(Problem.kingdom, func.count(Problem.id))
        .group_by(Problem.kingdom)
        .order_by(func.count(Problem.id).desc())
    )
    by_kingdom = [{"name": row[0], "count": row[1]} for row in kingdom_result.all()]

    # 解答代码覆盖率
    solutions_result = await db.execute(
        select(func.count(Problem.id)).where(Problem.solutions != "{}")
    )
    with_solutions = solutions_result.scalar() or 0

    return {
        "total_problems": total,
        "by_difficulty": by_difficulty,
        "by_kingdom": by_kingdom,
        "with_solutions": with_solutions,
        "solution_coverage": f"{with_solutions}/{total} ({round(with_solutions/total*100, 1)}%)" if total else "0",
        "total_kingdoms": len(by_kingdom),
    }
