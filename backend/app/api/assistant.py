"""
AI 助手 API - 智能对话、分级帮助
核心原则：LLM 调用成功后才扣金币（事务一致性）
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.assistant import AssistantMessage
from app.schemas.all import (
    AssistantRequest,
    HintRequest,
    AssistantResponse,
    ProblemBrief,
)
from app.services.auth import get_current_user
from app.services.agent import (
    build_help_messages,
    format_problem_context,
)
from app.services.llm import chat_completion, LLMServiceError, LLMNotConfiguredError
from app.services.problems import get_problem_detail
from app.services.search import semantic_search
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/assistant", tags=["AI助手"])

# 帮助等级对应消耗
LEVEL_COST = {
    "hint": settings.HINT_COST,
    "guide": settings.GUIDE_COST,
    "explain": settings.EXPLAIN_COST,
    "chat": 0,
}

# 免费打招呼语
FREE_GREETINGS = {"你好", "hello", "帮助", "help", "你是谁", "介绍一下"}


@router.post("/chat", response_model=AssistantResponse)
async def chat_with_assistant(
    request: AssistantRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """与 AI 助手自由对话（免费问候；其他消耗 1 金币）"""
    # 构建题目上下文
    problem_context_str = "无"
    if request.problem_id:
        problem = await get_problem_detail(db, request.problem_id)
        if problem:
            problem_context_str = format_problem_context(problem.model_dump())

    # 判断是否免费
    is_free = request.message.strip() in FREE_GREETINGS
    coins_to_spend = 0 if is_free else 1

    # 检查余额
    if coins_to_spend > 0 and user.coins < coins_to_spend:
        raise HTTPException(
            status_code=402,
            detail=f"金币不足！当前余额: {user.coins}💰",
        )

    # 构建消息并调用 LLM
    messages = build_help_messages(
        level="chat",
        user_message=request.message,
        problem_context=problem_context_str,
        conversation_history=request.history,
    )

    try:
        reply = await chat_completion(messages)
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # ✅ LLM 成功后，再扣金币 + 保存记录（一次提交保证原子性）
    if coins_to_spend > 0:
        user.coins -= coins_to_spend

    record = AssistantMessage(
        user_id=user.id,
        problem_id=request.problem_id,
        role="assistant",
        content=reply,
        help_level="chat",
        coins_spent=coins_to_spend,
        context_snapshot=json.dumps(
            {"problem_id": request.problem_id}, ensure_ascii=False
        ) if request.problem_id else None,
    )
    db.add(record)
    await db.commit()

    # 语义搜索相关题目（无论是否提到关键词，chat 模式都尝试推荐）
    related = None
    try:
        if request.message and len(request.message) > 10:
            search_results = semantic_search(request.message, top_k=3)
            related = [r.problem for r in search_results]
    except Exception:
        pass  # 搜索失败不影响主流程

    return AssistantResponse(
        message=reply,
        help_level="chat",
        coins_spent=coins_to_spend,
        coins_remaining=user.coins,
        related_problems=related,
    )


@router.post("/hint", response_model=AssistantResponse)
async def get_hint(
    request: HintRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取分级帮助（hint / guide / explain），消耗对应金币"""
    # 验证帮助等级
    if request.level not in LEVEL_COST:
        raise HTTPException(status_code=400, detail="无效的帮助等级")

    cost = LEVEL_COST[request.level]

    # 检查金币余额
    if user.coins < cost:
        raise HTTPException(
            status_code=402,
            detail=f"金币不足！当前余额: {user.coins}💰，需要: {cost}💰。去闯关赚金币吧~",
        )

    # 获取题目详情
    problem = await get_problem_detail(db, request.problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="题目不存在")

    problem_dict = problem.model_dump()
    problem_context_str = format_problem_context(problem_dict)

    # 构建消息
    user_message = "我需要帮助！" if request.level != "chat" else "你好呀~"
    messages = build_help_messages(
        level=request.level,
        user_message=user_message,
        problem_context=problem_context_str,
        conversation_history=request.conversation_history,
    )

    # ✅ 先调用 LLM，成功后再扣金币
    try:
        reply = await chat_completion(messages)
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # LLM 成功 → 扣除金币 + 保存记录
    user.coins -= cost

    record = AssistantMessage(
        user_id=user.id,
        problem_id=request.problem_id,
        role="assistant",
        content=reply,
        help_level=request.level,
        coins_spent=cost,
        context_snapshot=json.dumps(
            {"problem_id": request.problem_id, "level": request.level},
            ensure_ascii=False,
        ),
    )
    db.add(record)
    await db.commit()

    # 详解模式：推荐相关题目
    related = None
    if request.level == "explain":
        try:
            related_query = f"类似 {problem_dict['title_cn']} 的题目"
            search_results = semantic_search(related_query, top_k=3)
            related = [
                r.problem for r in search_results
                if r.problem.id != request.problem_id
            ][:2]
        except Exception:
            pass

    return AssistantResponse(
        message=reply,
        help_level=request.level,
        coins_spent=cost,
        coins_remaining=user.coins,
        related_problems=related,
    )


@router.get("/history")
async def get_chat_history(
    problem_id: str | None = None,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户与AI助手的对话历史"""
    query = select(AssistantMessage).where(
        AssistantMessage.user_id == user.id
    )

    if problem_id:
        query = query.where(AssistantMessage.problem_id == problem_id)

    query = query.order_by(
        AssistantMessage.created_at.desc()
    ).limit(limit)

    result = await db.execute(query)
    history = result.scalars().all()

    return [
        {
            "id": m.id,
            "problem_id": m.problem_id,
            "role": m.role,
            "content": m.content,
            "help_level": m.help_level,
            "coins_spent": m.coins_spent,
            "created_at": m.created_at.isoformat(),
        }
        for m in reversed(history)
    ]
