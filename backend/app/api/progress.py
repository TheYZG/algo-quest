"""
进度 & 提交 API
使用显式事务边界确保数据一致性
"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.submission import Submission
from app.schemas.all import (
    SubmissionRequest,
    SubmissionResponse,
    SubmissionListResponse,
)
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/progress", tags=["进度"])

# 难度对应的金币奖励
DIFFICULTY_BONUS = {"Easy": 5, "Medium": 10, "Hard": 20}


@router.post("/submit", response_model=SubmissionResponse)
async def submit_solution(
    request: SubmissionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    提交代码

    当前版本为模拟评测（实际评测需 Docker sandbox）。
    AC 时奖励金币并更新用户统计。所有操作在一个事务中。
    """
    # 注意：显式事务边界由 db.begin() 提供
    # 当函数正常返回时自动 commit，异常时自动 rollback

    # 模拟评测
    import random
    is_accepted = random.random() < 0.85
    status = "accepted" if is_accepted else "wrong_answer"
    coins_earned = 0

    if is_accepted:
        # 检查是否首次 AC
        check_result = await db.execute(
            select(Submission).where(
                and_(
                    Submission.user_id == user.id,
                    Submission.problem_id == request.problem_id,
                    Submission.status == "accepted",
                )
            )
        )
        first_ac = check_result.scalar_one_or_none() is None

        if first_ac:
            # 查询题目难度
            from app.services.problems import get_problem_detail
            problem = await get_problem_detail(db, request.problem_id)
            diff = problem.difficulty if problem else "Medium"
            coins_earned = DIFFICULTY_BONUS.get(diff, 10)

            # 更新用户统计
            user.coins += coins_earned
            user.total_solved += 1
            if diff == "Easy":
                user.easy_solved += 1
            elif diff == "Hard":
                user.hard_solved += 1
            else:
                user.medium_solved += 1

    # 创建提交记录
    submission = Submission(
        user_id=user.id,
        problem_id=request.problem_id,
        problem_title=request.problem_title,
        status=status,
        language=request.language,
        code=request.code,
        result="Accepted" if is_accepted else "Wrong Answer",
        coins_earned=coins_earned,
    )
    db.add(submission)

    # 一次 commit 提交所有变更（AC时：user统计 + submission记录）
    await db.commit()
    await db.refresh(submission)

    return SubmissionResponse(
        id=submission.id,
        problem_id=request.problem_id,
        status=status,
        language=request.language,
        result=submission.result,
        coins_earned=coins_earned,
        created_at=submission.created_at,
    )


@router.get("/submissions", response_model=SubmissionListResponse)
async def list_submissions(
    problem_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取提交记录（分页）"""
    # 使用聚合查询获取总数（避免全量加载到内存）
    count_query = select(func.count()).select_from(Submission).where(
        Submission.user_id == user.id
    )
    if problem_id:
        count_query = count_query.where(Submission.problem_id == problem_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    query = select(Submission).where(Submission.user_id == user.id)
    if problem_id:
        query = query.where(Submission.problem_id == problem_id)

    query = query.order_by(desc(Submission.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    submissions = result.scalars().all()

    return SubmissionListResponse(
        total=total,
        submissions=[
            SubmissionResponse.model_validate(s) for s in submissions
        ],
    )


@router.get("/solved")
async def get_solved_problems(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户已解决的题目ID列表"""
    result = await db.execute(
        select(Submission.problem_id)
        .where(
            and_(
                Submission.user_id == user.id,
                Submission.status == "accepted",
            )
        )
        .distinct()
    )
    return {"solved": list(result.scalars().all())}
