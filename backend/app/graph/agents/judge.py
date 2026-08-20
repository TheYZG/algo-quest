"""
判题官 ⚖️ / 复核官 🛡️ / 仲裁 — 判题子图三节点
Judge 提示词迁移自 app/services/judge.py；Reviewer 以对抗视角复核；
分歧时 resolve_verdict 确定性加权（复核官对抗视角可信度略高）
"""
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from app.graph.llm import get_chat_model
from app.graph.state import ParliamentState, make_timeline_event
from app.graph.tools import get_problem_detail, get_reference_solution

REVIEW_THRESHOLD = 0.7  # 低于此置信度触发复核


class JudgeVerdict(BaseModel):
    """判题结构化裁决"""
    correct: bool = Field(description="用户代码是否正确")
    confidence: float = Field(description="判断置信度 0.0-1.0")
    analysis: str = Field(default="", description="整体分析（中文，200字内）")
    issues: list[str] = Field(default_factory=list, description="具体问题列表")
    suggestions: list[str] = Field(default_factory=list, description="改进建议列表")
    comparison: str = Field(default="", description="与参考解答的核心差异（中文，100字内）")


JUDGE_PROMPT = """你是「算法大陆议会」的判题官⚖️，资深算法竞赛评审专家。

任务：
1. 调用工具获取题目详情与参考解答
2. 对比用户提交的代码与官方参考解答
3. 给出结构化裁决

判定标准（严格）：
- ✅ CORRECT：算法思路正确，能处理所有边界情况，时间/空间复杂度合理
- ❌ INCORRECT：存在逻辑错误、遗漏边界情况、复杂度不达标、或完全错误

注意：
- 用户代码与参考解答算法相同但实现细节不同（变量名等）仍视为正确
- 暴力解法若能通过题目的规模约束也算正确，但可在 suggestions 里提示优化
"""

REVIEWER_PROMPT = """你是「算法大陆议会」的复核官🛡️，独立质检专家。

你的任务是复核判题官的裁决——请带着"判题官可能判错了"的对抗视角：
1. 调用工具重新获取题目与参考解答
2. 独立分析用户代码，不参考判题官的分析结论
3. 重点检查判题官容易犯的错：把正确判为错误（边界情况误判）、把错误判为正确（忽略隐藏 bug、复杂度超标）

给出你自己的结构化裁决。宁可推翻也要基于代码事实，不盲从原判。
"""


def needs_review(judge_result: dict | None) -> bool:
    """低置信度 或 判定错误 → 触发复核"""
    if not judge_result:
        return False
    return judge_result.get("confidence", 1.0) < REVIEW_THRESHOLD or not judge_result.get("correct", False)


def resolve_verdict(judge_result: dict, review_verdict: dict | None) -> dict:
    """
    仲裁裁决（确定性规则，无 LLM）：
    - 无复核 → 采纳判题官
    - 一致 → 采纳判题官，置信度取两者较高，标记 reviewed
    - 分歧 → 倾向复核官（对抗视角可信度略高），标记 arbitrated
    """
    if review_verdict is None:
        return dict(judge_result)

    if judge_result["correct"] == review_verdict["correct"]:
        final = dict(judge_result)
        final["confidence"] = max(judge_result["confidence"], review_verdict["confidence"])
        final["reviewed"] = True
        return final

    # 分歧：倾向复核官，但保留判题官分析供参考
    final = dict(review_verdict)
    final["arbitrated"] = True
    final["judge_opinion"] = judge_result["analysis"]
    final["analysis"] = (
        f"判题官与复核官意见分歧，仲裁采纳复核官结论。"
        f"复核分析：{review_verdict['analysis']}"
    )
    return final


def _build_judge_agent():
    return create_react_agent(
        get_chat_model(),
        tools=[get_problem_detail, get_reference_solution],
        state_modifier=JUDGE_PROMPT,
        response_format=JudgeVerdict,
    )


def _build_reviewer_agent():
    return create_react_agent(
        get_chat_model(),
        tools=[get_problem_detail, get_reference_solution],
        state_modifier=REVIEWER_PROMPT,
        response_format=JudgeVerdict,
    )


def _verdict_task_prompt(state: ParliamentState, extra: str) -> str:
    return "\n".join([
        extra,
        f"题目编号：{state.get('problem_id')}",
        f"提交语言：{state.get('language') or 'python'}",
        f"用户代码：\n{state.get('user_code') or ''}",
    ])


async def _run_structured_agent(agent, prompt: str) -> dict:
    result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
    verdict = result.get("structured_response")
    if verdict is None:
        raise RuntimeError("判题 Agent 未返回结构化裁决")
    if hasattr(verdict, "model_dump"):  # Pydantic → dict
        verdict = verdict.model_dump()
    return dict(verdict)


def make_judge_node(agent=None):
    """判题官节点（可注入 agent 供测试）"""
    model_agent = agent or _build_judge_agent()

    async def judge_node(state: ParliamentState) -> dict:
        timeline = list(state.get("timeline") or [])
        timeline.append(make_timeline_event(type="agent_start", agent="judge", action="开始评审代码"))
        start = time.time()
        prompt = _verdict_task_prompt(state, "请评审以下提交：")
        verdict = await _run_structured_agent(model_agent, prompt)
        review = needs_review(verdict)
        timeline.append(make_timeline_event(
            type="agent_done", agent="judge",
            action=f"裁决：{'正确' if verdict['correct'] else '错误'}（置信度 {verdict['confidence']:.2f}）"
                   + ("，触发复核" if review else ""),
            duration_ms=int((time.time() - start) * 1000),
        ))
        return {
            "judge_result": verdict,
            "needs_review": review,
            "timeline": timeline,
        }

    return judge_node


def make_reviewer_node(agent=None):
    """复核官节点（可注入 agent 供测试）"""
    model_agent = agent or _build_reviewer_agent()

    async def reviewer_node(state: ParliamentState) -> dict:
        timeline = list(state.get("timeline") or [])
        timeline.append(make_timeline_event(type="agent_start", agent="reviewer", action="对抗视角复核"))
        start = time.time()
        prompt = _verdict_task_prompt(state, "请独立复核以下提交（判题官已有初步裁决，但你必须独立判断）：")
        verdict = await _run_structured_agent(model_agent, prompt)
        timeline.append(make_timeline_event(
            type="agent_done", agent="reviewer",
            action=f"复核裁决：{'正确' if verdict['correct'] else '错误'}（置信度 {verdict['confidence']:.2f}）",
            duration_ms=int((time.time() - start) * 1000),
        ))
        return {"review_verdict": verdict, "timeline": timeline}

    return reviewer_node
