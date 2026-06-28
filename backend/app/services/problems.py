"""
题目数据服务 - 从 SQLite 主存储查询，ChromaDB 用于语义搜索
"""
import json
import logging
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.problem import Problem
from app.schemas.all import ProblemBrief, ProblemDetail, ProblemListResponse
from app.services.importer import KINGDOM_CONFIG

logger = logging.getLogger(__name__)


# ============================================================
# 工具函数
# ============================================================
def _parse_kingdoms(raw_kingdoms: str) -> list[str]:
    """解析 kingdoms JSON 字段为王国名列表"""
    if not raw_kingdoms:
        return []
    try:
        kingdoms_data = json.loads(raw_kingdoms)
        # 格式: [["数据结构工坊","🔧"], ["混沌领域","🌪️"]] -> ["数据结构工坊","混沌领域"]
        if kingdoms_data and isinstance(kingdoms_data[0], list):
            return [k[0] for k in kingdoms_data]
        return kingdoms_data
    except Exception:
        return []


def _row_to_brief(row: Problem) -> ProblemBrief:
    """Problem ORM 对象 -> ProblemBrief Pydantic"""
    tags_list = json.loads(row.tags) if row.tags else []
    kingdoms_list = _parse_kingdoms(row.kingdoms)
    return ProblemBrief(
        id=row.id,
        number=row.number,
        title=row.title,
        title_cn=row.title_cn,
        slug=row.slug,
        difficulty=row.difficulty,
        tags=tags_list,
        ac_rate=row.ac_rate,
        kingdom=row.kingdom,
        kingdom_emoji=row.kingdom_emoji,
        kingdoms=kingdoms_list,
    )


def _row_to_detail(row: Problem) -> ProblemDetail:
    """Problem ORM 对象 -> ProblemDetail Pydantic"""
    tags_list = json.loads(row.tags) if row.tags else []
    hints_list = json.loads(row.hints) if row.hints else []
    solutions_dict = json.loads(row.solutions) if row.solutions else {}
    kingdoms_list = _parse_kingdoms(row.kingdoms)
    return ProblemDetail(
        id=row.id,
        number=row.number,
        title=row.title,
        title_cn=row.title_cn,
        slug=row.slug,
        difficulty=row.difficulty,
        tags=tags_list,
        description_html=row.description_html,
        description_cn_html=row.description_cn_html,
        likes=row.likes,
        dislikes=row.dislikes,
        accepted=row.accepted,
        submissions=row.submissions_count,
        hints=hints_list,
        solutions=solutions_dict,
        kingdom=row.kingdom,
        kingdom_emoji=row.kingdom_emoji,
        kingdoms=kingdoms_list,
    )


# ============================================================
# 查询方法（需要 db session）
# ============================================================

async def get_problem_detail(db: AsyncSession, problem_id: str) -> Optional[ProblemDetail]:
    """获取单个题目的完整信息"""
    result = await db.execute(
        select(Problem).where(Problem.id == problem_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return _row_to_detail(row)


async def get_problem_by_number(db: AsyncSession, number: int) -> Optional[ProblemDetail]:
    """按题号获取题目"""
    result = await db.execute(
        select(Problem).where(Problem.number == number)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return _row_to_detail(row)


async def get_problems_list(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    difficulty: Optional[str] = None,
    kingdom: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> ProblemListResponse:
    """获取题目列表（分页 + 筛选，按题号排序）"""
    from sqlalchemy import literal

    conditions = []

    if difficulty:
        conditions.append(Problem.difficulty == difficulty)

    # kingdom 筛选 — 基于 kingdoms 多王国归属 JSON 字段
    if kingdom:
        conditions.append(Problem.kingdoms.like(f'%{kingdom}%'))

    # 计数查询
    count_stmt = select(func.count(Problem.id))
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # 数据查询
    stmt = select(Problem).order_by(Problem.number)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # tag 过滤在 SQL 外完成（SQLite JSON 查询受限）
    problems = []
    for row in rows:
        if tags:
            row_tags = json.loads(row.tags) if row.tags else []
            if not any(t in row_tags for t in tags):
                continue
        problems.append(_row_to_brief(row))

    return ProblemListResponse(
        total=total,
        page=page,
        page_size=page_size,
        problems=problems,
    )


async def get_kingdoms(db: AsyncSession) -> list[dict]:
    """获取所有算法王国及其实时统计数据 + 完整视觉配置
    基于 kingdoms（多王国归属）展开统计，每道题在每个归属王国中都被计入"""
    # 全量加载后在 Python 中展开 kingdoms JSON 统计
    stmt = select(Problem.kingdoms, Problem.difficulty)
    result = await db.execute(stmt)
    rows = result.all()

    # Python 展开聚合 — 每道题按其全部归属王国计数
    by_kingdom: dict[str, dict] = {}
    for kingdoms_json, diff in rows:
        try:
            kingdom_entries = json.loads(kingdoms_json)  # [["数据结构工坊","🔧"],["混沌领域","🌪️"]]
        except Exception:
            continue
        if not kingdom_entries or not isinstance(kingdom_entries, list):
            continue
        # 处理 [[name,emoji], ...] 格式
        if isinstance(kingdom_entries[0], list):
            entries = {k[0]: k[1] for k in kingdom_entries}
        else:
            entries = {k: "" for k in kingdom_entries}

        for k_name, k_emoji in entries.items():
            if k_name not in by_kingdom:
                by_kingdom[k_name] = {
                    "name": k_name,
                    "emoji": k_emoji,
                    "total_problems": 0,
                    "easy_count": 0,
                    "medium_count": 0,
                    "hard_count": 0,
                }
            by_kingdom[k_name]["total_problems"] += 1
            if diff == "Easy":
                by_kingdom[k_name]["easy_count"] += 1
            elif diff == "Hard":
                by_kingdom[k_name]["hard_count"] += 1
            else:
                by_kingdom[k_name]["medium_count"] += 1

    # 合并 KINGDOM_CONFIG 视觉属性
    kingdoms = []
    for kdata in by_kingdom.values():
        name = kdata["name"]
        config = KINGDOM_CONFIG.get(name, {})
        kingdoms.append({
            "id": config.get("id", name),
            "name": name,
            "emoji": config.get("emoji", kdata["emoji"]),
            "color": config.get("color", "#94a3b8"),
            "bg": config.get("bg", "#1a1c20"),
            "glow": config.get("glow", "rgba(148,163,184,.25)"),
            "chaos": config.get("chaos", False),
            "tags": [],
            "total_problems": kdata["total_problems"],
            "easy_count": kdata["easy_count"],
            "medium_count": kdata["medium_count"],
            "hard_count": kdata["hard_count"],
        })

    kingdoms.sort(key=lambda k: k["total_problems"], reverse=True)
    return kingdoms


async def get_tags_stats(db: AsyncSession) -> list[dict]:
    """获取所有标签及题目数量——由于标签存储在 JSON 中，不做精确聚合，
    改为全量加载后在内存中统计（题目量不大，可接受）"""
    result = await db.execute(select(Problem.tags, Problem.kingdom))
    rows = result.all()

    tag_counts: dict[str, dict] = {}
    for tags_str, kingdom in rows:
        tags_list = json.loads(tags_str) if tags_str else []
        for tag in tags_list:
            if tag not in tag_counts:
                tag_counts[tag] = {"tag": tag, "count": 0, "kingdom": kingdom}
            tag_counts[tag]["count"] += 1

    return sorted(tag_counts.values(), key=lambda x: x["count"], reverse=True)


async def get_all_problem_ids(db: AsyncSession) -> list[str]:
    """获取所有题目 ID 列表（用于进度追踪）"""
    result = await db.execute(select(Problem.id).order_by(Problem.number))
    return [row[0] for row in result.all()]
