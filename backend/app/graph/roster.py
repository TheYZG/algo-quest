"""议会 Agent 名册 — 后端路由 / 前端议会面板共用"""

AGENT_ROSTER = [
    {
        "id": "queen",
        "name": "精灵女王",
        "emoji": "👑",
        "role": "Supervisor",
        "description": "议会首脑：理解你的意图，拆解任务，调度专家，汇总仲裁。",
    },
    {
        "id": "tutor",
        "name": "导师",
        "emoji": "🎓",
        "role": "Tutor",
        "description": "三级教学帮助：思路提示、部分引导、完整详解。",
    },
    {
        "id": "judge",
        "name": "判题官",
        "emoji": "⚖️",
        "role": "Judge",
        "description": "评审你的代码：对比参考解答，指出问题与改进建议。",
    },
    {
        "id": "scout",
        "name": "侦察兵",
        "emoji": "🔭",
        "role": "Scout",
        "description": "情报专家：语义搜题，侦察你的做题进度与卡题历史。",
    },
    {
        "id": "planner",
        "name": "军师",
        "emoji": "🗺️",
        "role": "Planner",
        "description": "战略顾问：分析弱点王国，制定学习规划与复盘建议。",
    },
    {
        "id": "reviewer",
        "name": "复核官",
        "emoji": "🛡️",
        "role": "Reviewer",
        "description": "判题质检：低置信度时以对抗视角二次验证，降低误判。",
    },
]


def get_agent(agent_id: str) -> dict | None:
    for a in AGENT_ROSTER:
        if a["id"] == agent_id:
            return a
    return None
