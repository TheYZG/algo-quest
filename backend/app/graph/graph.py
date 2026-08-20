"""
议会图组装 — parliament_graph（完整循环）与 judge_graph（判题子图）
- Queen 为中心：条件边路由到专家，专家回到 Queen 循环派单
- Summarize 收尾：单专家产出直通（省一次 LLM 调用），多专家 LLM 汇总
- AsyncSqliteSaver checkpointer：thread_id = user_id:problem_id 跨请求记忆
"""
import logging
import os
from typing import Optional

import aiosqlite
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.config import get_settings
from app.graph.agents.judge import (
    make_judge_node, make_reviewer_node, needs_review, resolve_verdict,
)
from app.graph.agents.queen import make_queen_node
from app.graph.agents.specialists import build_specialists, make_specialist_node
from app.graph.llm import get_chat_model
from app.graph.state import ParliamentState, make_timeline_event
from app.graph.utils import parse_json_block

logger = logging.getLogger(__name__)

MAX_DISPATCH_ROUNDS = 3  # 最多派单轮数（防死循环）

CHECKPOINT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "parliament_checkpoints.db",
)


# ============================================================
# Summarize 收尾节点
# ============================================================

SUMMARIZE_PROMPT = """你是「算法大陆议会」的精灵女王👑，现在议会专家已完成任务，请汇总给用户。

规则：
- 以女王的口吻转述专家结论，开头可用一句简短调度说明（如"我请导师看了你的代码～"）
- 保留专家答复的核心内容，不丢失技术细节
- 简洁，300 字内
直接输出给用户的内容，不要任何前后缀说明。"""


def make_summarize_node(llm=None):
    model = llm or get_chat_model(streaming=True)

    async def summarize_node(state: ParliamentState) -> dict:
        timeline = list(state.get("timeline") or [])
        outputs = state.get("agent_outputs") or {}
        user_facing = [v for k, v in outputs.items() if k in ("tutor", "planner")]

        # 直通优化：唯一面向用户的产出直接作为回复（不额外调 LLM）
        if len(user_facing) == 1:
            final_reply = user_facing[0]
        elif outputs:
            parts = "\n\n".join(f"[{k} 的答复]\n{v}" for k, v in outputs.items())
            messages = [
                SystemMessage(content=SUMMARIZE_PROMPT),
                HumanMessage(content=f"用户问题：{state['messages'][-1].content if state['messages'] else '（无）'}\n\n专家产出：\n{parts}"),
            ]
            # 打 final_reply 标签：SSE 端点按此标签做 token 级流式
            final_reply = model.with_config(tags=["final_reply"]).invoke(messages).content
        else:
            final_reply = "议会暂时没有可用的答复，请稍后再试～"

        timeline.append(make_timeline_event(type="final", agent="queen", action="汇总完成"))
        return {"final_reply": final_reply, "timeline": timeline, "current_agent": None}

    return summarize_node


# ============================================================
# 判题仲裁节点（review 完成后调用）
# ============================================================

def make_arbitrate_node():
    async def arbitrate_node(state: ParliamentState) -> dict:
        timeline = list(state.get("timeline") or [])
        final = resolve_verdict(state["judge_result"], state.get("review_verdict"))
        timeline.append(make_timeline_event(
            type="arbitrate", agent="queen",
            action="仲裁完成" + ("（采纳复核官）" if final.get("arbitrated") else "（维持原判）"),
        ))
        return {"judge_result": final, "timeline": timeline}

    return arbitrate_node


# ============================================================
# 路由函数
# ============================================================

def _route_from_queen(state: ParliamentState) -> str:
    nxt = state.get("current_agent") or "finish"
    # 防死循环：派单轮数超限时强制收工
    dispatch_rounds = sum(1 for ev in (state.get("timeline") or []) if ev.get("agent") == "queen" and ev.get("type") == "agent_start")
    if dispatch_rounds > MAX_DISPATCH_ROUNDS * 2:
        return "summarize"
    if nxt == "finish":
        return "summarize"
    return nxt if nxt in ("scout", "tutor", "planner", "judge") else "summarize"


def _route_after_judge(state: ParliamentState) -> str:
    if state.get("needs_review") and not state.get("review_verdict"):
        return "reviewer"
    return "queen"


def _route_after_reviewer(state: ParliamentState) -> str:
    jr, rv = state.get("judge_result"), state.get("review_verdict")
    if jr and rv and jr.get("correct") != rv.get("correct"):
        return "arbitrate"
    return "queen"


# ============================================================
# 图构建
# ============================================================

def build_parliament_graph(llm=None, agents: Optional[dict] = None, checkpointer=None):
    """构建完整议会图（可注入 llm/agents/checkpointer 供测试）"""
    queen = make_queen_node(llm=llm)
    summarize = make_summarize_node(llm=llm)
    arbitrate = make_arbitrate_node()

    if agents is None:
        agents = build_specialists()
    judge_node = make_judge_node(agent=agents.get("judge"))
    reviewer_node = make_reviewer_node(agent=agents.get("reviewer"))

    g = StateGraph(ParliamentState)
    g.add_node("queen", queen)
    g.add_node("scout", make_specialist_node("scout", agent=agents.get("scout")))
    g.add_node("tutor", make_specialist_node("tutor", agent=agents.get("tutor")))
    g.add_node("planner", make_specialist_node("planner", agent=agents.get("planner")))
    g.add_node("judge", judge_node)
    g.add_node("reviewer", reviewer_node)
    g.add_node("arbitrate", arbitrate)
    g.add_node("summarize", summarize)

    g.add_edge(START, "queen")
    g.add_conditional_edges("queen", _route_from_queen, {
        "scout": "scout", "tutor": "tutor", "planner": "planner",
        "judge": "judge", "summarize": "summarize",
    })
    for spec in ("scout", "tutor", "planner"):
        g.add_edge(spec, "queen")
    g.add_conditional_edges("judge", _route_after_judge, {"reviewer": "reviewer", "queen": "queen"})
    g.add_conditional_edges("reviewer", _route_after_reviewer, {"arbitrate": "arbitrate", "queen": "queen"})
    g.add_edge("arbitrate", "queen")
    g.add_edge("summarize", END)
    return g.compile(checkpointer=checkpointer)


def build_judge_graph(judge_agent=None, reviewer_agent=None):
    """构建判题子图：Judge → (条件) Reviewer → Arbitrate → END（供 /progress/submit 直调）"""
    g = StateGraph(ParliamentState)
    g.add_node("judge", make_judge_node(agent=judge_agent))
    g.add_node("reviewer", make_reviewer_node(agent=reviewer_agent))
    g.add_node("arbitrate", make_arbitrate_node())

    g.add_edge(START, "judge")
    g.add_conditional_edges("judge", lambda s: "reviewer" if s.get("needs_review") else END,
                            {"reviewer": "reviewer", END: END})
    # 一致/分歧的复核结果都要经 arbitrate 合并置信度（resolve_verdict 内处理）
    g.add_edge("reviewer", "arbitrate")
    g.add_edge("arbitrate", END)
    return g.compile()


# ============================================================
# Checkpointer 单例
# ============================================================

_compiled_parliament = None
_checkpointer = None


async def get_checkpointer() -> AsyncSqliteSaver:
    """获取 AsyncSqliteSaver 单例（async 工厂，Task 10 API 层会直接用到）

    为什么必须 async：AsyncSqliteSaver.__init__ 调用 asyncio.get_running_loop()
    并把 saver 绑定到当前事件循环（同步版本 get_tuple/put 经
    run_coroutine_threadsafe 回投到该 loop），进程内无运行循环时构造会直接抛
    RuntimeError，因此不能在同步工厂中构建。

    连接策略：aiosqlite.connect() 惰性建连——首个 checkpoint 操作时各异步方法
    自动 await self.setup()（幂等，内含 `await self.conn` 完成真正建连与建表），
    故此处无需显式 setup。
    """
    global _checkpointer
    if _checkpointer is None:
        os.makedirs(os.path.dirname(CHECKPOINT_DB), exist_ok=True)
        _checkpointer = AsyncSqliteSaver(aiosqlite.connect(CHECKPOINT_DB))
    return _checkpointer


async def get_parliament_graph():
    """获取带 checkpointer 的议会图单例（须在事件循环内调用，如 FastAPI lifespan）"""
    global _compiled_parliament
    if _compiled_parliament is None:
        _compiled_parliament = build_parliament_graph(checkpointer=await get_checkpointer())
    return _compiled_parliament


def make_thread_config(user_id, problem_id=None) -> dict:
    """构造 checkpointer thread 配置"""
    return {"configurable": {"thread_id": f"{user_id}:{problem_id or 'global'}"},
            "recursion_limit": 20}
