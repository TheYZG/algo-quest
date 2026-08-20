"""
精灵女王 Supervisor — 议会编排核心
职责：意图识别 → 派单（可多轮循环）→ 决定收工
路由决策由 LLM 以 JSON 输出；pinned_level 时直派 tutor（确定性路径）
"""
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.graph.llm import get_chat_model
from app.graph.state import ParliamentState, make_timeline_event
from app.graph.utils import parse_json_block

logger = logging.getLogger(__name__)

VALID_NEXT = {"scout", "tutor", "planner", "judge", "finish"}

QUEEN_SYSTEM_PROMPT = """你是「算法大陆议会」的精灵女王👑，议会调度者。

议会专家名册：
- scout 侦察兵🔭：语义搜题、查询用户进度与卡题历史
- tutor 导师🎓：三级教学帮助（hint 思路提示 / guide 部分引导 / explain 完整详解）
- planner 军师🗺️：学习规划、弱点王国分析、复盘建议
- judge 判题官⚖️：评审用户代码正确性（仅在用户明确要求判题/看代码问题时派）

你的决策规则：
1. 分析用户最新消息 + 当前状态（已有专家产出、判题结果等）
2. 用户带代码求助 → 建议先派 scout 侦察历史，再派 tutor 教学
3. 纯闲聊/简单提问 → 可直接 next=finish（由 summarize 节点回应）
4. 搜题需求 → scout；规划/复盘需求 → planner；判题需求 → judge
5. 所需专家都已产出（agent_outputs 已含足够信息）→ next=finish
6. 最多派单 3 轮，必须收敛到 finish

你必须只返回 JSON（不要 markdown 代码块）：
{
  "intent": "teaching|search|planning|judging|chat",
  "next": "scout|tutor|planner|judge|finish",
  "task_brief": "给该专家的任务说明（一句话，含关键上下文）",
  "help_level": "hint|guide|explain|null"
}
"""


def _build_route_prompt(state: ParliamentState) -> str:
    parts = [f"用户最新消息：{state['messages'][-1].content if state['messages'] else '（无）'}"]
    if state.get("problem_id"):
        parts.append(f"当前题目：{state['problem_id']}")
    if state.get("user_code"):
        parts.append(f"用户代码（截断）：{state['user_code'][:800]}")
    if state.get("agent_outputs"):
        done = "; ".join(f"{k}: {v[:200]}" for k, v in state["agent_outputs"].items())
        parts.append(f"已完成的专家产出：{done}")
    if state.get("judge_result"):
        parts.append(f"判题结果：{state['judge_result']}")
    return "\n".join(parts)


def make_queen_node(llm=None):
    """构建 Queen 节点（可注入 llm 供测试）"""
    model = llm or get_chat_model()

    async def queen_node(state: ParliamentState) -> dict:
        timeline = list(state.get("timeline") or [])

        # 确定性路径：/hint 固定级别 → 直派 tutor
        if state.get("pinned_level"):
            timeline.append(make_timeline_event(
                type="agent_start", agent="queen",
                action=f"女王受理请求，指派导师（{state['pinned_level']}）",
            ))
            return {
                "intent": "teaching",
                "current_agent": "tutor",
                "task_brief": f"用户请求 {state['pinned_level']} 级帮助",
                "timeline": timeline,
            }

        # LLM 路由决策
        messages = [
            SystemMessage(content=QUEEN_SYSTEM_PROMPT),
            HumanMessage(content=_build_route_prompt(state)),
        ]
        try:
            reply = model.invoke(messages).content
            decision = parse_json_block(reply) or {}
        except Exception as e:
            logger.error(f"Queen 路由失败，降级 finish: {e}")
            decision = {}

        nxt = decision.get("next") if decision.get("next") in VALID_NEXT else "finish"
        intent = decision.get("intent") or "chat"
        brief = decision.get("task_brief") or ""

        timeline.append(make_timeline_event(
            type="agent_start", agent="queen",
            action=f"识别意图「{intent}」，派单 {nxt}" if nxt != "finish" else "汇总收工",
        ))
        return {
            "intent": intent,
            "current_agent": nxt,
            "task_brief": brief,
            "timeline": timeline,
        }

    return queen_node
