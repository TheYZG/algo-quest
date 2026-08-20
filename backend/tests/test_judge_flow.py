"""判题/复核/仲裁测试"""
from langchain_core.messages import AIMessage

from app.graph.agents.judge import (
    needs_review, resolve_verdict, make_judge_node, make_reviewer_node,
)


def _verdict(correct, confidence):
    return {
        "correct": correct, "confidence": confidence, "analysis": "分析",
        "issues": [], "suggestions": [], "comparison": "对比",
    }


def test_低置信度触发复核():
    assert needs_review(_verdict(True, 0.5)) is True


def test_判错触发复核():
    assert needs_review(_verdict(False, 0.9)) is True


def test_高置信度正确不触发():
    assert needs_review(_verdict(True, 0.95)) is False


def test_无复核时采纳判题官():
    final = resolve_verdict(_verdict(True, 0.9), None)
    assert final["correct"] is True


def test_一致时采纳并提升置信度():
    final = resolve_verdict(_verdict(False, 0.7), _verdict(False, 0.9))
    assert final["correct"] is False
    assert final["confidence"] == 0.9
    assert final.get("reviewed") is True


def test_分歧且复核官判对时倾向复核官():
    final = resolve_verdict(_verdict(False, 0.75), _verdict(True, 0.95))
    # 对抗视角可信度略高：分歧时倾向复核官
    assert final["correct"] is True
    assert final.get("arbitrated") is True


class FakeStructuredAgent:
    def __init__(self, verdict: dict):
        self.verdict = verdict

    async def ainvoke(self, payload, config=None):
        return {"messages": [AIMessage(content="ok")], "structured_response": self.verdict}


def _judge_state():
    return {
        "messages": [], "user_id": "u1", "problem_id": "0001",
        "user_code": "class Solution: ...", "language": "python",
        "intent": "judging", "pinned_level": None, "current_agent": "judge",
        "task_brief": "判题", "agent_outputs": {},
        "judge_result": None, "review_verdict": None, "needs_review": False,
        "final_reply": "", "timeline": [], "coins_to_spend": 0,
    }


async def test_judge节点写入结构化结果():
    node = make_judge_node(agent=FakeStructuredAgent(_verdict(True, 0.99)))
    delta = await node(_judge_state())
    assert delta["judge_result"]["correct"] is True
    assert delta["needs_review"] is False


async def test_reviewer节点写入复核结果():
    node = make_reviewer_node(agent=FakeStructuredAgent(_verdict(True, 0.95)))
    delta = await node(_judge_state())
    assert delta["review_verdict"]["confidence"] == 0.95
