"""ParliamentState 与 timeline 事件工厂测试"""
from app.graph.state import ParliamentState, make_timeline_event


def test_state_必填字段可构造():
    state: ParliamentState = {
        "messages": [],
        "user_id": "u1",
        "problem_id": "0001",
        "user_code": None,
        "language": None,
        "intent": None,
        "pinned_level": None,
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
    assert state["user_id"] == "u1"


def test_timeline事件包含完整字段():
    ev = make_timeline_event(
        type="agent_start", agent="scout", action="侦察用户进度"
    )
    assert ev["agent"] == "scout"
    assert ev["type"] == "agent_start"
    assert ev["action"] == "侦察用户进度"
    assert "ts" in ev


def test_timeline事件done类型带时长():
    ev = make_timeline_event(
        type="agent_done", agent="scout", action="完成", duration_ms=120
    )
    assert ev["duration_ms"] == 120
