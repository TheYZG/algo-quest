"""专家节点测试（注入假 ReAct Agent）"""
from langchain_core.messages import AIMessage

from app.graph.agents.specialists import make_specialist_node, build_specialists


class FakeAgent:
    def __init__(self, reply: str):
        self.reply = reply
        self.inputs = []

    async def ainvoke(self, payload, config=None):
        self.inputs.append(payload)
        return {"messages": [AIMessage(content=self.reply)]}


def _base_state():
    return {
        "messages": [], "user_id": "u1", "problem_id": "0001",
        "user_code": None, "language": None, "intent": "teaching",
        "pinned_level": "hint", "current_agent": "tutor",
        "task_brief": "给个提示", "agent_outputs": {},
        "judge_result": None, "review_verdict": None, "needs_review": False,
        "final_reply": "", "timeline": [], "coins_to_spend": 0,
    }


async def test_专家节点记录产出与时间线():
    fake = FakeAgent("考虑用哈希表优化查找～")
    node = make_specialist_node("tutor", agent=fake)
    delta = await node(_base_state())
    assert delta["agent_outputs"]["tutor"] == "考虑用哈希表优化查找～"
    evs = delta["timeline"]
    assert any(e["type"] == "agent_done" and e["agent"] == "tutor" for e in evs)
    # 任务简报要传给 Agent（带上下文）
    assert "给个提示" in fake.inputs[0]["messages"][-1].content


async def test_专家失败降级不中断():
    class BoomAgent:
        async def ainvoke(self, payload, config=None):
            raise RuntimeError("LLM 挂了")

    node = make_specialist_node("tutor", agent=BoomAgent())
    delta = await node(_base_state())
    assert "暂时离线" in delta["agent_outputs"]["tutor"]
    assert delta["timeline"]  # 失败也记录事件


async def test_构建全部专家():
    specs = build_specialists()
    assert set(specs.keys()) == {"tutor", "scout", "planner"}
