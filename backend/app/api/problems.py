"""
题目 API - 列表、详情、搜索（从 SQLite 查询，ChromaDB 用于语义搜索）
"""
from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.all import (
    ProblemListResponse,
    ProblemDetail,
    SearchRequest,
    SearchResponse,
)
from app.services.problems import (
    get_problems_list,
    get_problem_detail,
    get_kingdoms,
    get_tags_stats,
)
from app.services.search import semantic_search

router = APIRouter(prefix="/api/problems", tags=["题目"])


@router.get("", response_model=ProblemListResponse)
async def list_problems(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    difficulty: str = Query(default=None, description="Easy / Medium / Hard"),
    kingdom: str = Query(default=None, description="算法王国名称"),
    tags: str = Query(default=None, description="标签，逗号分隔"),
    db: AsyncSession = Depends(get_db),
):
    """获取题目列表（分页 + 筛选）"""
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    return await get_problems_list(
        db=db,
        page=page,
        page_size=page_size,
        difficulty=difficulty,
        kingdom=kingdom,
        tags=tag_list,
    )


@router.get("/{problem_id}", response_model=ProblemDetail)
async def get_problem(
    problem_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取题目详情"""
    from fastapi import HTTPException
    problem = await get_problem_detail(db, problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return problem


@router.get("/meta/kingdoms")
async def list_kingdoms(
    db: AsyncSession = Depends(get_db),
):
    """获取所有算法王国（实时统计数据）"""
    return await get_kingdoms(db)


@router.get("/meta/tags")
async def list_tags(
    db: AsyncSession = Depends(get_db),
):
    """获取所有标签"""
    return await get_tags_stats(db)


@router.post("/search", response_model=SearchResponse)
async def search_problems(request: SearchRequest):
    """AI 语义搜索题目（不使用 DB，直接调 ChromaDB）"""
    results = semantic_search(
        query=request.query,
        top_k=request.top_k,
        difficulty=request.difficulty,
        tags=request.tags,
    )

    return SearchResponse(
        query=request.query,
        results=results,
        total=len(results),
    )
