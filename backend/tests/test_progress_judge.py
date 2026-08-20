"""progress 判题接入议会子图测试"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class FakeUser:
    id = "u1"
    coins = 20
    total_solved = 0
    easy_solved = 0
    medium_solved = 0
    hard_solved = 0


@pytest.fixture
def client():
    from app.main import app
    from app.services.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: FakeUser()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _judge_graph_result(correct=True, confidence=0.95, arbitrated=False):
    return {
        "judge_result": {
            "correct": correct, "confidence": confidence,
            "analysis": "分析", "issues": [], "suggestions": [],
            "comparison": "", "arbitrated": arbitrated, "reviewed": arbitrated,
        },
        "review_verdict": {"correct": True, "confidence": 0.95} if arbitrated else None,
        "timeline": [{"type": "agent_done", "agent": "judge", "action": "裁决", "ts": 1}],
        "agent_outputs": {},
        "final_reply": "",
    }


def test_提交返回ai_feedback含复核信息(client):
    fake_graph = AsyncMock()
    fake_graph.ainvoke = AsyncMock(return_value=_judge_graph_result(arbitrated=True))
    with patch("app.api.progress.get_judge_graph", return_value=fake_graph), \
         patch("app.api.progress._get_reference_solution",
               AsyncMock(return_value=("ref", "题目", "描述"))):
        resp = client.post("/api/progress/submit", json={
            "problem_id": "0001", "problem_title": "Two Sum",
            "language": "python", "code": "print(1)",
        })
    assert resp.status_code == 200
    fb = resp.json()["ai_feedback"]
    assert fb["execution_mode"] == "ai"
    assert fb.get("reviewed") is True
