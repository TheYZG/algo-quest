"""
议会专家 Agent — Tutor / Scout / Planner
每个专家 = create_react_agent（ReAct 循环 + 工具调用）+ 世界观人格提示词
节点函数记录产出与 timeline 事件；单专家失败降级不中断整体编排
"""
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from app.graph.llm import get_chat_model
from app.graph.state import ParliamentState, make_timeline_event
from app.graph.tools import (
    get_problem_detail,
    get_reference_solution,
    semantic_search_problems,
    get_user_progress,
    get_weak_kingdoms_tool,
)

# ============================================================
# 人格与职责提示词（Tutor 迁移自 app/services/agent.py）
# ============================================================

TUTOR_PROMPT = """你是「算法大陆议会」的导师🎓，来自算法大陆的可爱精灵教师！

你的性格：
- 活泼热情，擅长用生动的比喻解释抽象算法
- 鼓励用户思考，而不是直接给答案
- 说话带游戏感："勇者！""冒险者！""加油～✨"

帮助分级规则（严格遵守）：
- 【hint 提示】只给 1-2 个思路方向，不给具体解法步骤或代码，150 字内
- 【guide 引导】给核心思路 + 伪代码 + 易踩坑提醒，不给完整可运行代码，250 字左右
- 【explain 详解】完整解析：考察点、思路、参考代码（默认 Python）、复杂度分析、举例走一遍

其他规则：
- 始终用中文回复，保持精灵语气
- 可调用工具获取题目详情和参考题解（explain 级别前先看参考题解）
- 若收到侦察兵的情报（如用户 WA 历史），针对性调整提示内容
"""

SCOUT_PROMPT = """你是「算法大陆议会」的侦察兵🔭，情报专家。

职责：
- 语义搜题：调用搜索工具，用自然语言找题（如"类似背包问题的 DP 入门题"）
- 进度侦察：查询用户做题统计、当前题的尝试历史（WA 次数、最后状态）
- 输出简明情报摘要（200 字内），供女王和导师决策使用

规则：只陈述事实情报，不教学、不给解题提示。始终用中文。
"""

PLANNER_PROMPT = """你是「算法大陆议会」的军师🗺️，战略顾问。

职责：
- 调用进度/弱点工具分析用户薄弱王国
- 结合语义搜索推荐合适的练习题
- 产出学习规划：今日目标、推荐题目（带编号和难度）、复盘建议

规则：规划要具体可执行（题目用 4 位编号），语气专业带一点军师风格。始终用中文。
"""


def _build_tutor():
    return create_react_agent(
        get_chat_model(),
        tools=[get_problem_detail, get_reference_solution],
        state_modifier=TUTOR_PROMPT,
    )


def _build_scout():
    return create_react_agent(
        get_chat_model(),
        tools=[semantic_search_problems, get_user_progress],
        state_modifier=SCOUT_PROMPT,
    )


def _build_planner():
    return create_react_agent(
        get_chat_model(),
        tools=[get_user_progress, get_weak_kingdoms_tool, semantic_search_problems],
        state_modifier=PLANNER_PROMPT,
    )


AGENT_BUILDERS = {
    "tutor": _build_tutor,
    "scout": _build_scout,
    "planner": _build_planner,
}


def build_specialists() -> dict:
    """构建三个专家 Agent 实例 {name: agent}"""
    return {name: builder() for name, builder in AGENT_BUILDERS.items()}


def make_specialist_node(name: str, agent=None):
    """构建专家节点（可注入 agent 供测试）"""
    model_agent = agent or AGENT_BUILDERS[name]()

    async def specialist_node(state: ParliamentState) -> dict:
        timeline = list(state.get("timeline") or [])
        timeline.append(make_timeline_event(
            type="agent_start", agent=name, action="开始执行任务",
        ))
        start = time.time()

        # 组装任务指令：Queen 的派单简报 + 关键上下文
        task_parts = [f"女王派单任务：{state.get('task_brief') or '（无说明）'}"]
        if state.get("pinned_level") and name == "tutor":
            task_parts.append(f"帮助级别：【{state['pinned_level']}】（严格按此级别回复）")
        if state.get("problem_id"):
            task_parts.append(f"当前题目编号：{state['problem_id']}（可用工具查询详情）")
        if state.get("user_code"):
            task_parts.append(f"用户当前代码（可能不完整）：\n{state['user_code'][:1500]}")
        if state.get("agent_outputs"):
            others = "; ".join(
                f"[{k}] {v[:300]}" for k, v in state["agent_outputs"].items() if k != name
            )
            if others:
                task_parts.append(f"其他专家已提供的情报：{others}")
        task_parts.append(f"用户最新消息：{state['messages'][-1].content if state['messages'] else '（无）'}")

        messages = [
            SystemMessage(content="你是议会专家，请完成任务并直接给出面向用户的最终答复。"),
            HumanMessage(content="\n".join(task_parts)),
        ]

        outputs = dict(state.get("agent_outputs") or {})
        try:
            result = await model_agent.ainvoke({"messages": messages})
            reply = result["messages"][-1].content
        except Exception as e:
            # 降级：记录离线说明，不中断编排
            reply = f"（{name} 专家暂时离线：{e}）"
            timeline.append(make_timeline_event(
                type="agent_done", agent=name, action="执行失败（已降级）",
                duration_ms=int((time.time() - start) * 1000),
            ))
            outputs[name] = reply
            return {"agent_outputs": outputs, "timeline": timeline}

        timeline.append(make_timeline_event(
            type="agent_done", agent=name, action="任务完成",
            duration_ms=int((time.time() - start) * 1000),
        ))
        outputs[name] = reply
        return {"agent_outputs": outputs, "timeline": timeline}

    return specialist_node
