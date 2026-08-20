"""图组装测试：Queen→Scout→Queen→Tutor→Queen→Summarize 完整循环"""
import json
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.graph.graph import build_parliament_graph, build_judge_graph
from app.graph.agents.queen import make_queen_node


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)

    def invoke(self, messages):
        return AIMessage(content=self.replies.pop(0))


class FakeAgent:
    def __init__(self, reply):
        self.reply = reply

    async def ainvoke(self, payload, config=None):
        return {"messages": [AIMessage(content=self.reply)]}


def _input():
    return {
        "messages": [HumanMessage(content="我卡了，帮我看看")],
        "user_id": "u1", "problem_id": "0001", "user_code": "x=1",
        "language": "python", "intent": None, "pinned_level": None,
        "current_agent": None, "task_brief": "", "agent_outputs": {},
        "judge_result": None, "review_verdict": None, "needs_review": False,
        "final_reply": "", "timeline": [], "coins_to_spend": 0,
    }


async def test_议会图完整循环_多专家协作():
    # Queen 三次决策：派 scout → 派 tutor → finish；summarize 直通单专家产出
    queen_llm = FakeLLM([
        json.dumps({"intent": "teaching", "next": "scout", "task_brief": "查进度", "help_level": "hint"}),
        json.dumps({"intent": "teaching", "next": "tutor", "task_brief": "给提示", "help_level": "hint"}),
        json.dumps({"intent": "teaching", "next": "finish", "task_brief": "", "help_level": "hint"}),
    ])
    graph = build_parliament_graph(
        llm=queen_llm,
        agents={
            "scout": FakeAgent("该用户此题 WA 2 次"),
            "tutor": FakeAgent("试试哈希表～"),
            "planner": FakeAgent("规划"),
        },
    )
    result = await graph.ainvoke(_input())
    # 两专家产出都在
    assert "scout" in result["agent_outputs"]
    assert "tutor" in result["agent_outputs"]
    # final_reply 来自 tutor（唯一面向用户的产出直通）
    assert result["final_reply"] == "试试哈希表～"
    # timeline 覆盖完整协作链
    agents_seen = {ev["agent"] for ev in result["timeline"]}
    assert {"queen", "scout", "tutor"} <= agents_seen


async def test_议会图_pinned直通tutor():
    graph = build_parliament_graph(
        llm=FakeLLM([]),
        agents={
            "scout": FakeAgent("s"), "tutor": FakeAgent("直通提示"),
            "planner": FakeAgent("p"),
        },
    )
    inp = _input()
    inp["pinned_level"] = "hint"
    result = await graph.ainvoke(inp)
    assert result["agent_outputs"]["tutor"] == "直通提示"
    assert "scout" not in result["agent_outputs"]


async def test_判题子图_高置信度不触发复核():
    from tests.test_judge_flow import FakeStructuredAgent, _verdict

    judge_graph = build_judge_graph(
        judge_agent=FakeStructuredAgent(_verdict(True, 0.99)),
        reviewer_agent=FakeStructuredAgent(_verdict(True, 0.99)),
    )
    inp = _input()
    inp["intent"] = "judging"
    result = await judge_graph.ainvoke(inp)
    assert result["judge_result"]["correct"] is True
    assert result["review_verdict"] is None  # 未触发复核


async def test_判题子图_低置信度触发复核并仲裁():
    from tests.test_judge_flow import FakeStructuredAgent, _verdict

    judge_graph = build_judge_graph(
        judge_agent=FakeStructuredAgent(_verdict(False, 0.5)),
        reviewer_agent=FakeStructuredAgent(_verdict(True, 0.95)),
    )
    inp = _input()
    inp["intent"] = "judging"
    result = await judge_graph.ainvoke(inp)
    assert result["review_verdict"] is not None
    assert result["judge_result"]["arbitrated"] is True
    assert result["judge_result"]["correct"] is True  # 仲裁倾向复核官
