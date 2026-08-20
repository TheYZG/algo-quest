"""Agent 名册测试"""
from app.graph.roster import AGENT_ROSTER, get_agent


def test_名册包含常驻5个Agent():
    ids = {a["id"] for a in AGENT_ROSTER}
    assert {"queen", "tutor", "judge", "scout", "planner"} <= ids


def test_get_agent按ID查询():
    a = get_agent("tutor")
    assert a["name"] == "导师"
    assert a["emoji"]
    assert a["description"]


def test_未知Agent返回None():
    assert get_agent("nope") is None
