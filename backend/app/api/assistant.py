"""
AI 助手 API — 议会多 Agent 编排入口
核心原则：图执行成功后才扣金币（事务一致性）
- POST /chat            JSON 响应（含 timeline / agents_involved，向后兼容）
- POST /chat/stream     SSE 流式（timeline 事件 + final）
- POST /hint            固定级别帮助（pinned_level 直通导师）
- GET  /agents          议会名册
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
from app.services.llm import LLMNotConfiguredError, LLMServiceError
from app.services.search import semantic_search
from app.config import get_settings
from app.graph.graph import get_parliament_graph, make_thread_config
from app.graph.roster import AGENT_ROSTER

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/assistant", tags=["AI助手"])

LEVEL_COST = {
    "hint": settings.HINT_COST,
    "guide": settings.GUIDE_COST,
    "explain": settings.EXPLAIN_COST,
    "chat": 0,
}

FREE_GREETINGS = {"你好", "hello", "帮助", "help", "你是谁", "介绍一下"}


def _base_graph_input(request, user: User, pinned_level: str | None) -> dict:
    """构造图的初始 State"""
    from langchain_core.messages import HumanMessage, AIMessage

    # AssistantRequest.history / HintRequest.conversation_history 均为 dict 列表
    history = getattr(request, "history", None) or getattr(
        request, "conversation_history", None
    )
    messages = []
    for h in (history or [])[-6:]:
        if h.get("role") == "assistant":
            messages.append(AIMessage(content=h.get("content", "")))
        else:
            messages.append(HumanMessage(content=h.get("content", "")))
    messages.append(HumanMessage(content=request.message))

    problem_context = getattr(request, "problem_context", None) or {}
    return {
        "messages": messages,
        "user_id": user.id,
        "problem_id": getattr(request, "problem_id", None),
        "user_code": problem_context.get("code"),
        "language": problem_context.get("language"),
        "intent": None,
        "pinned_level": pinned_level,
        "current_agent": None,
        "task_brief": "",
        "agent_outputs": {},
        "judge_result": None,
        "review_verdict": None,
        "needs_review": False,
        "final_reply": "",
        "timeline": [],
        "coins_to_spend": 0,
    }


async def _settle_coins(user: User, db: AsyncSession, coins: int,
                         request, level: str, reply: str) -> None:
    """图执行成功后：扣金币 + 保存记录（一次提交保证原子性）"""
    if coins > 0:
        user.coins -= coins
    record = AssistantMessage(
        user_id=user.id,
        problem_id=getattr(request, "problem_id", None),
        role="assistant",
        content=reply,
        help_level=level,
        coins_spent=coins,
        context_snapshot=json.dumps(
            {"problem_id": getattr(request, "problem_id", None), "level": level},
            ensure_ascii=False,
        ) if getattr(request, "problem_id", None) else None,
    )
    db.add(record)
    await db.commit()


async def _related_problems(message: str, exclude_id: str | None) -> list | None:
    try:
        if message and len(message) > 10:
            results = semantic_search(message, top_k=3)
            return [r.problem for r in results if r.problem.id != exclude_id][:2]
    except Exception:
        pass
    return None


@router.post("/chat", response_model=AssistantResponse)
async def chat_with_assistant(
    request: AssistantRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """与议会自由对话（免费问候；其他消耗 1 金币）"""
    is_free = request.message.strip() in FREE_GREETINGS
    coins_to_spend = 0 if is_free else 1

    if coins_to_spend > 0 and user.coins < coins_to_spend:
        raise HTTPException(status_code=402, detail=f"金币不足！当前余额: {user.coins}💰")

    graph = await get_parliament_graph()
    graph_input = _base_graph_input(request, user, pinned_level=None)
    graph_input["coins_to_spend"] = coins_to_spend

    try:
        result = await graph.ainvoke(
            graph_input, config=make_thread_config(user.id, request.problem_id)
        )
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))

    reply = result["final_reply"]
    timeline = result.get("timeline") or []
    agents_involved = list((result.get("agent_outputs") or {}).keys())

    await _settle_coins(user, db, coins_to_spend, request, "chat", reply)

    return AssistantResponse(
        message=reply,
        help_level="chat",
        coins_spent=coins_to_spend,
        coins_remaining=user.coins,
        related_problems=await _related_problems(request.message, request.problem_id),
        timeline=timeline,
        agents_involved=agents_involved,
    )


@router.post("/chat/stream")
async def chat_with_assistant_stream(
    request: AssistantRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """议会对话 SSE 流式端点

    事件格式（data: JSON\n\n）：
    - {"type": "timeline", ...}   协作时间线事件
    - {"type": "final", ...}      最终结构化结果（含 message/coins/timeline）
    """
    is_free = request.message.strip() in FREE_GREETINGS
    coins_to_spend = 0 if is_free else 1

    if coins_to_spend > 0 and user.coins < coins_to_spend:
        raise HTTPException(status_code=402, detail=f"金币不足！当前余额: {user.coins}💰")

    async def event_stream():
        graph = await get_parliament_graph()
        graph_input = _base_graph_input(request, user, pinned_level=None)
        graph_input["coins_to_spend"] = coins_to_spend
        config = make_thread_config(user.id, request.problem_id)

        final_state = {}
        try:
            async for update in graph.astream(graph_input, config=config,
                                               stream_mode="updates"):
                for node, delta in update.items():
                    if not isinstance(delta, dict):
                        continue
                    for ev in (delta.get("timeline") or []):
                        yield f"data: {json.dumps({'type': 'timeline', **ev}, ensure_ascii=False)}\n\n"
                    if "final_reply" in delta:
                        final_state.update(delta)
            # 图执行完成 → 结算金币
            reply = final_state.get("final_reply", "")
            await _settle_coins(user, db, coins_to_spend, request, "chat", reply)
            payload = {
                "type": "final",
                "message": reply,
                "coins_spent": coins_to_spend,
                "coins_remaining": user.coins,
                "timeline": final_state.get("timeline") or [],
                "agents_involved": list((final_state.get("agent_outputs") or {}).keys()),
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except LLMNotConfiguredError as e:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)}, ensure_ascii=False)}\n\n"
        except LLMServiceError as e:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/hint", response_model=AssistantResponse)
async def get_hint(
    request: HintRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取分级帮助（hint / guide / explain），固定级别直通导师"""
    if request.level not in LEVEL_COST:
        raise HTTPException(status_code=400, detail="无效的帮助等级")

    cost = LEVEL_COST[request.level]
    if user.coins < cost:
        raise HTTPException(
            status_code=402,
            detail=f"金币不足！当前余额: {user.coins}💰，需要: {cost}💰。去闯关赚金币吧～",
        )

    graph = await get_parliament_graph()
    graph_input = _base_graph_input(request, user, pinned_level=request.level)
    graph_input["coins_to_spend"] = cost

    try:
        result = await graph.ainvoke(
            graph_input, config=make_thread_config(user.id, request.problem_id)
        )
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))

    reply = result["final_reply"]

    await _settle_coins(user, db, cost, request, request.level, reply)

    related = None
    if request.level == "explain":
        related = await _related_problems("算法题目推荐", request.problem_id)

    return AssistantResponse(
        message=reply,
        help_level=request.level,
        coins_spent=cost,
        coins_remaining=user.coins,
        related_problems=related,
        timeline=result.get("timeline") or [],
        agents_involved=["queen", "tutor"],
    )


@router.get("/agents")
async def get_agents():
    """议会 Agent 名册（前端议会面板渲染用）"""
    return {"agents": AGENT_ROSTER}


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
