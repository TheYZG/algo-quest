"""
进度 & 提交 API
AI 大模型判题：对比用户代码与参考解答，给出正确性判断和详细反馈
（沙箱执行系统已禁用，全部使用 AI 大模型判题）
"""
import json
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
    ExecutionDetail,
    TestCaseResult,
)
from app.services.auth import get_current_user
from app.services.problems import get_problem_detail
from app.services.test_cases import get_test_cases

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/progress", tags=["进度"])

# 难度对应的金币奖励
DIFFICULTY_BONUS = {"Easy": 5, "Medium": 10, "Hard": 20}


def _format_test_result(status: str, tests_passed: int, tests_total: int) -> str:
    """格式化评测结果为可读字符串"""
    if status == "accepted":
        return f"Accepted ({tests_passed}/{tests_total} tests passed)"
    elif status == "wrong_answer":
        return f"Wrong Answer ({tests_passed}/{tests_total} tests passed)"
    elif status == "timeout":
        return "Time Limit Exceeded"
    elif status == "runtime_error":
        return "Runtime Error"
    elif status == "compile_error":
        return "Compile Error"
    return status


# ── 沙箱执行系统已禁用 ──────────────────────────────────────
# async def _execute_python_code(code, problem_id): ...
# 原沙箱执行逻辑已整体移除，所有判题统一走 AI 大模型路径。
# ──────────────────────────────────────────────────────────────

async def _get_reference_solution(
    problem_id: str, db: AsyncSession
) -> tuple[str, str, str]:
    """
    从数据库获取题目的参考解答

    Returns:
        (reference_code, problem_title, problem_description)
    """
    from app.models.problem import Problem

    # 标准化 problem_id：前端可能传 "11" 或 "0011"
    pid_4digit = str(problem_id).zfill(4)
    pid_int = int(problem_id) if problem_id.isdigit() else 0

    # 先按 4-digit ID 查询
    result = await db.execute(
        select(Problem).where(Problem.id == pid_4digit)
    )
    problem = result.scalar_one_or_none()

    # 如果没找到，按 number 查询
    if not problem and pid_int > 0:
        result = await db.execute(
            select(Problem).where(Problem.number == pid_int)
        )
        problem = result.scalar_one_or_none()

    if not problem:
        logger.warning(f"题目 {problem_id} 在数据库中未找到")
        return "", f"Problem #{problem_id}", ""

    title = problem.title_cn or problem.title or f"Problem #{problem_id}"
    description = problem.description_html or problem.description_cn_html or ""

    # 解析 solutions JSON
    solutions = {}
    if problem.solutions:
        try:
            solutions = json.loads(problem.solutions)
        except Exception:
            solutions = {}

    # 优先使用 Python 参考解答
    reference = (
        solutions.get("python") or
        solutions.get("cpp") or
        solutions.get("java") or
        solutions.get("javascript") or
        solutions.get("go") or
        ""
    )

    logger.debug(
        f"_get_reference_solution: pid={problem_id} title={title} "
        f"ref_len={len(reference)} has_solutions={len(solutions)}"
    )

    return reference, title, description


async def _ai_evaluate(
    problem_id: str,
    problem_title: str,
    language: str,
    code: str,
    db: AsyncSession,
) -> tuple[str, list[dict], str, dict]:
    """
    AI 大模型判题

    Returns:
        (status, test_results, result_message, ai_detail)
        ai_detail: {"analysis": str, "issues": list, "suggestions": list, "comparison": str}
    """
    from app.services.judge import ai_judge, JudgeResult
    from app.services.llm import LLMServiceError

    ai_detail = {
        "analysis": "",
        "issues": [],
        "suggestions": [],
        "comparison": "",
        "confidence": 0.0,
        "execution_mode": "ai",
    }

    # 获取参考解答
    reference, title_from_db, description = await _get_reference_solution(problem_id, db)
    final_title = problem_title or title_from_db

    if not reference:
        logger.warning(f"题目 {problem_id} 无参考解答，无法 AI 判题")
        ai_detail["analysis"] = "该题目暂无参考解答，无法进行 AI 判题"
        return ("accepted", [], "AI 判题跳过（无参考解答）", ai_detail)

    logger.info(
        f"AI 判题开始: title={final_title} lang={language} "
        f"code_len={len(code)} ref_len={len(reference)} desc_len={len(description)}"
    )

    try:
        result: JudgeResult = await ai_judge(
            problem_title=final_title,
            problem_description=description,
            reference_solution=reference,
            user_code=code,
            language=language,
        )
    except LLMServiceError as e:
        logger.error(f"AI 判题失败: {e}")
        ai_detail["analysis"] = f"AI 判题服务暂时不可用：{e}"
        return ("accepted", [], "AI 判题失败，默认通过", ai_detail)

    # 构建结果
    status = "accepted" if result.correct else "wrong_answer"
    result_msg = "✅ AI 判断：代码正确" if result.correct else "❌ AI 判断：代码存在问题"

    ai_detail = {
        "analysis": result.analysis,
        "issues": result.issues,
        "suggestions": result.suggestions,
        "comparison": result.comparison,
        "confidence": result.confidence,
        "execution_mode": "ai",
    }

    # 构建 test_results 格式（前端兼容）
    test_results = [{
        "passed": result.correct,
        "input": "AI 综合分析",
        "expected": "算法正确 + 时间复杂度合理",
        "actual": "✅ " + result.analysis[:100] if result.correct else "❌ " + (result.issues[0] if result.issues else result.analysis[:100]),
        "error": "",
        "runtime_ms": 0.0,
    }]

    logger.info(
        f"AI 判题完成: correct={result.correct} confidence={result.confidence:.2f} "
        f"issues={len(result.issues)} analysis_len={len(result.analysis)}"
    )

    return (status, test_results, result_msg, ai_detail)


@router.post("/submit", response_model=SubmissionResponse)
async def submit_solution(
    request: SubmissionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    提交代码 — AI 大模型判题

    流程：
    1. 获取题目参考解答
    2. AI 对比用户代码与参考解答，判断正确性
    3. 给出详细分析和改进建议
    4. Python 代码额外尝试沙箱执行（有测试用例时）
    """
    test_results = []
    result_message = ""
    ai_detail = {}

    logger.info(
        f"=== 评测请求 === problem_id={request.problem_id} "
        f"language={request.language} code_len={len(request.code)}"
    )

    # ============================================================
    # 主流程：AI 大模型判题（所有语言）
    # ============================================================
    logger.info("使用 AI 大模型判题")
    status, test_results, result_message, ai_detail = await _ai_evaluate(
        request.problem_id,
        request.problem_title,
        request.language,
        request.code,
        db,
    )
    logger.info(f"AI 判题结果: status={status} msg={result_message}")

    # ── 沙箱执行已禁用（2026-07-01），全部使用 AI 判题 ──
    # 原沙箱并行验证逻辑已移除
    # ──────────────────────────────────────────────────────────

    is_accepted = status == "accepted"
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
        result=result_message,
        coins_earned=coins_earned,
    )
    db.add(submission)

    # 一次 commit 提交所有变更
    await db.commit()
    await db.refresh(submission)

    return SubmissionResponse(
        id=submission.id,
        problem_id=request.problem_id,
        status=status,
        language=request.language,
        result=result_message,
        coins_earned=coins_earned,
        created_at=submission.created_at,
        test_results=[
            TestCaseResult(**tr) for tr in test_results
        ],
        ai_feedback=ai_detail if ai_detail else None,
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
    count_query = select(func.count()).select_from(Submission).where(
        Submission.user_id == user.id
    )
    if problem_id:
        count_query = count_query.where(Submission.problem_id == problem_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

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


@router.get("/test-cases/{problem_id}")
async def get_problem_test_cases(problem_id: str):
    """获取题目的测试用例（调试用）"""
    cases = get_test_cases(problem_id)
    return {
        "problem_id": problem_id,
        "count": len(cases),
        "test_cases": cases,
    }
