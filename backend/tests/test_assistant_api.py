"""assistant API 层测试（mock 议会图）"""
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class FakeUser:
    id = "u1"
    coins = 20


class FakeDB:
    """能 add/commit 的假 session"""
    def add(self, obj):
        pass

    async def commit(self):
        pass


@pytest.fixture
def client():
    from app.main import app
    from app.services.auth import get_current_user
    from app.database import get_db
    app.dependency_overrides[get_current_user] = lambda: FakeUser()
    app.dependency_overrides[get_db] = lambda: FakeDB()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _fake_graph_result():
    return {
        "messages": [], "final_reply": "议会答复～", "timeline": [
            {"type": "agent_start", "agent": "queen", "action": "受理", "ts": 1},
            {"type": "agent_done", "agent": "tutor", "action": "完成", "ts": 2, "duration_ms": 100},
        ],
        "agent_outputs": {"tutor": "议会答复～"},
    }


def test_chat返回timeline与agents(client):
    fake_graph = AsyncMock()
    fake_graph.ainvoke = AsyncMock(return_value=_fake_graph_result())
    with patch("app.api.assistant.get_parliament_graph", new=AsyncMock(return_value=fake_graph)):
        resp = client.post("/api/assistant/chat", json={
            "message": "你好呀，这题怎么想", "problem_id": "0001",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "议会答复～"
    assert data["timeline"] and data["timeline"][0]["agent"] == "queen"
    assert "tutor" in data["agents_involved"]


def test_agents名册端点(client):
    resp = client.get("/api/assistant/agents")
    assert resp.status_code == 200
    ids = {a["id"] for a in resp.json()["agents"]}
    assert "queen" in ids and "tutor" in ids


async def aiter_updates(*args, **kwargs):
    """模拟 astream(stream_mode='updates') 的更新流"""
    yield {"queen": {"timeline": [{"type": "agent_start", "agent": "queen", "action": "受理", "ts": 1}]}}
    yield {"tutor": {"timeline": [{"type": "agent_done", "agent": "tutor", "action": "完成", "ts": 2}],
                     "agent_outputs": {"tutor": "答复"}}}
    yield {"summarize": {"final_reply": "最终答复", "timeline": []}}


def test_chat_stream_SSE格式(client):
    fake_graph = AsyncMock()
    fake_graph.astream = aiter_updates
    with patch("app.api.assistant.get_parliament_graph", new=AsyncMock(return_value=fake_graph)):
        resp = client.post("/api/assistant/chat/stream", json={
            "message": "帮我看看这题", "problem_id": "0001",
        })
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert "data:" in body and "timeline" in body
