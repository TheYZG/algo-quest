"""Queen 路由节点测试（注入 FakeLLM）"""
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.graph.agents.queen import make_queen_node, QUEEN_SYSTEM_PROMPT


class FakeLLM:
    """按脚本顺序返回路由 JSON 的假模型"""
    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=self.replies.pop(0))


def _base_state(**kw):
    s = {
        "messages": [HumanMessage(content="我卡了，帮我看看")],
        "user_id": "u1", "problem_id": "0001", "user_code": "print(1)",
        "language": "python", "intent": None, "pinned_level": None,
        "current_agent": None, "task_brief": "", "agent_outputs": {},
        "judge_result": None, "review_verdict": None, "needs_review": False,
        "final_reply": "", "timeline": [], "coins_to_spend": 0,
    }
    s.update(kw)
    return s


async def test_queen路由到侦察兵():
    fake = FakeLLM([json.dumps({
        "intent": "teaching", "next": "scout",
        "task_brief": "侦察该用户在此题的 WA 历史", "help_level": "hint",
    })])
    node = make_queen_node(llm=fake)
    delta = await node(_base_state())
    assert delta["intent"] == "teaching"
    assert delta["current_agent"] == "scout"
    assert "WA" in delta["task_brief"]
    # 派单要记录 timeline 事件
    assert any(ev["agent"] == "queen" for ev in delta["timeline"])


async def test_queen连续派单到finish():
    fake = FakeLLM([
        json.dumps({"intent": "teaching", "next": "scout", "task_brief": "查进度", "help_level": "hint"}),
        json.dumps({"intent": "teaching", "next": "tutor", "task_brief": "针对性提示", "help_level": "hint"}),
        json.dumps({"intent": "teaching", "next": "finish", "task_brief": "", "help_level": "hint"}),
    ])
    node = make_queen_node(llm=fake)
    state = _base_state()
    d1 = await node(state); state.update(d1)
    d2 = await node(state); state.update(d1); state.update(d2)
    d3 = await node(state)
    assert d3["current_agent"] == "finish"


async def test_pinned_level直接派tutor不调LLM():
    fake = FakeLLM([])
    node = make_queen_node(llm=fake)
    delta = await node(_base_state(pinned_level="hint"))
    assert delta["current_agent"] == "tutor"
    assert fake.calls == []  # 未消耗 LLM 调用


async def test_路由JSON解析失败时降级finish():
    fake = FakeLLM(["这不是JSON"])
    node = make_queen_node(llm=fake)
    delta = await node(_base_state())
    assert delta["current_agent"] == "finish"
