# 「算法大陆议会」多 Agent 编排实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 LangGraph 将现有单次 LLM 调用的助手/判题升级为 Supervisor 编排的多 Agent 协作系统（Queen + 4 专家 + 条件复核），并以前端议会时间线展示协作过程。

**Architecture:** FastAPI 后端新增 `app/graph/` 包：`state.py`（共享 State）、`tools.py`（专家工具）、`agents/`（Queen 手写节点 + 专家 ReAct Agent + 判题/复核/仲裁）、`graph.py`（图组装 + AsyncSqliteSaver checkpointer）。`assistant.py`/`progress.py` API 改为调用图；新增 SSE 流式端点；前端 `quest-mode.html` 精灵面板升级为议会时间线。

**Tech Stack:** LangGraph 0.2.x（StateGraph / create_react_agent / AsyncSqliteSaver）、langchain-openai（ChatOpenAI，兼容 DeepSeek）、FastAPI StreamingResponse（SSE）、pytest + pytest-asyncio。

**设计文档:** `docs/superpowers/specs/2026-08-20-multi-agent-design.md`

**约定:**
- 所有命令均在 `backend/` 目录下执行（除标注外）。
- 每个任务完成后按步骤提交 git。
- `App.graph` 下所有新代码的 docstring 与注释使用中文，与现有代码风格一致。

---

### Task 1: 测试基础设施 + LangGraph 依赖

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/pytest.ini`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: 更新 requirements.txt**

在 `backend/requirements.txt` 末尾追加：

```text

# LangGraph 多 Agent 编排
langgraph==0.2.62
langgraph-checkpoint-sqlite==0.2.1
langchain-core==0.3.29
langchain-openai==0.2.14

# 测试
pytest==8.3.4
pytest-asyncio==0.25.0
```

- [ ] **Step 2: 安装依赖**

Run: `cd backend && pip install -r requirements.txt`
Expected: 全部安装成功，无版本冲突（openai 1.58.1 满足 langchain-openai 的 `>=1.58.1,<2` 约束）。

- [ ] **Step 3: 创建 pytest 配置**

`backend/pytest.ini`：

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
```

- [ ] **Step 4: 创建测试包骨架**

`backend/tests/__init__.py`：空文件。

`backend/tests/conftest.py`：

```python
"""测试夹具：事件循环由 pytest-asyncio auto 模式管理"""
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
```

- [ ] **Step 5: 验证 pytest 可运行**

Run: `cd backend && python -m pytest`
Expected: `no tests ran`（exit code 5），无收集错误。

- [ ] **Step 6: 验证 langgraph 导入**

Run: `cd backend && python -c "from langgraph.graph import StateGraph, START, END; from langgraph.prebuilt import create_react_agent; from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver; print('ok')"`
Expected: 输出 `ok`。

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/pytest.ini backend/tests/
git commit -m "chore: 添加 LangGraph 依赖与 pytest 测试基础设施"
```

---

### Task 2: ParliamentState 定义

**Files:**
- Create: `backend/app/graph/__init__.py`
- Create: `backend/app/graph/state.py`
- Test: `backend/tests/test_state.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_state.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.graph'`

- [ ] **Step 3: 实现 state.py**

`backend/app/graph/__init__.py`：空文件。

`backend/app/graph/state.py`：

```python
"""
议会共享状态 — LangGraph 全图流转的 State 定义
所有节点读写同一份 ParliamentState，timeline 记录协作事件流供前端渲染
"""
import time
from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages


class ParliamentState(TypedDict):
    """议会全局状态（total，非 partial——各节点返回增量 dict 由 LangGraph 合并）"""
    messages: Annotated[list, add_messages]   # 对话记忆（checkpointer 持久化）
    user_id: str
    problem_id: Optional[str]
    user_code: Optional[str]                  # 用户当前代码（求助/判题场景）
    language: Optional[str]                   # 提交语言
    intent: Optional[str]                     # Queen 识别的意图
    pinned_level: Optional[str]               # /hint 固定的帮助级别 hint/guide/explain
    current_agent: Optional[str]              # 当前执行的专家
    task_brief: str                           # Queen 派单时下发的任务上下文
    agent_outputs: dict                       # {agent_name: 产出文本}
    judge_result: Optional[dict]              # 判题官结构化裁决
    review_verdict: Optional[dict]            # 复核官结构化裁决
    needs_review: bool                        # 是否触发复核
    final_reply: str                          # 汇总回复
    timeline: list                            # 协作事件流
    coins_to_spend: int                       # API 层注入，图内不修改


def make_timeline_event(
    type: str,
    agent: str,
    action: str,
    duration_ms: int | None = None,
) -> dict:
    """构造一条协作时间线事件"""
    ev = {
        "type": type,        # agent_start / agent_done / arbitrate / final
        "agent": agent,      # queen / tutor / judge / scout / planner / reviewer
        "action": action,
        "ts": time.time(),
    }
    if duration_ms is not None:
        ev["duration_ms"] = duration_ms
    return ev
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_state.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph/ backend/tests/test_state.py
git commit -m "feat(graph): ParliamentState 共享状态与 timeline 事件工厂"
```

---

### Task 3: JSON 解析工具

Queen/Judge/仲裁节点要求 LLM 返回 JSON。提供健壮解析（容忍 ```json 代码块与前后杂文本），与现有 `judge.py` 的裸 JSON 约定一致。

**Files:**
- Create: `backend/app/graph/utils.py`
- Test: `backend/tests/test_utils.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_utils.py`：

```python
"""parse_json_block 健壮性测试"""
import pytest

from app.graph.utils import parse_json_block


def test_裸JSON():
    assert parse_json_block('{"a": 1}') == {"a": 1}


def test_markdown代码块包裹():
    text = '好的，这是结果：\n```json\n{"a": [1, 2]}\n```\n以上。'
    assert parse_json_block(text) == {"a": [1, 2]}


def test_前后杂文本():
    assert parse_json_block('前置说明 {"a": "b"} 后置说明') == {"a": "b"}


def test_非法输入返回None():
    assert parse_json_block("完全不是 JSON") is None
    assert parse_json_block("") is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_utils.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.graph.utils'`

- [ ] **Step 3: 实现 utils.py**

`backend/app/graph/utils.py`：

```python
"""图节点通用工具"""
import json
import re


def parse_json_block(text: str) -> dict | None:
    """从 LLM 回复中提取 JSON 对象（容忍 markdown 代码块与前后杂文本）"""
    if not text:
        return None
    # 1. 直接尝试
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    # 2. 提取 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    # 3. 提取首个 {...} 平衡块
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_utils.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph/utils.py backend/tests/test_utils.py
git commit -m "feat(graph): LLM 回复 JSON 健壮解析工具"
```

---

### Task 4: LLM 封装与 Agent 名册

**Files:**
- Create: `backend/app/graph/llm.py`
- Create: `backend/app/graph/roster.py`
- Test: `backend/tests/test_roster.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_roster.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_roster.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.graph.roster'`

- [ ] **Step 3: 实现 llm.py 与 roster.py**

`backend/app/graph/llm.py`：

```python
"""LangChain ChatModel 封装 — 复用现有 OpenAI 兼容配置（DeepSeek 等）"""
from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import get_settings


@lru_cache()
def get_chat_model(streaming: bool = False) -> ChatOpenAI:
    """构建 ChatOpenAI（兼容 DeepSeek / OpenAI / Ollama 等 base_url）"""
    settings = get_settings()
    if not settings.LLM_API_KEY:
        # 返回未配置模型，调用方在节点内抛 LLMNotConfiguredError
        pass
    return ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY or "not-configured",
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT,
        streaming=streaming,
    )
```

`backend/app/graph/roster.py`：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_roster.py -v`
Expected: 3 passed

- [ ] **Step 5: 验证 ChatModel 构建（不联网）**

Run: `cd backend && python -c "from app.graph.llm import get_chat_model; m = get_chat_model(); print(type(m).__name__)"`
Expected: 输出 `ChatOpenAI`

- [ ] **Step 6: Commit**

```bash
git add backend/app/graph/llm.py backend/app/graph/roster.py backend/tests/test_roster.py
git commit -m "feat(graph): ChatOpenAI 封装与议会 Agent 名册"
```

---

### Task 5: 工具层（专家 Agent 的双手）

工具在图节点内执行，无 FastAPI 依赖注入，自行开启 session（SQLite WAL 模式支持并发读）。`semantic_search` 为同步阻塞（ChromaDB + embedding），用 `asyncio.to_thread` 包装。

**Files:**
- Create: `backend/app/graph/tools.py`
- Test: `backend/tests/test_tools.py`

- [ ] **Step 1: 写失败测试（聚合逻辑 + session 工厂注入）**

`backend/tests/test_tools.py`：

```python
"""工具层测试：weak_kingdoms 聚合逻辑（注入内存 SQLite session 工厂）"""
import json

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.graph import tools as gt


class _Base(DeclarativeBase):
    pass


@pytest.fixture
async def session_factory():
    """内存数据库 + 最小表结构（复刻 Problem/Submission 关键列）"""
    from sqlalchemy import Column, String, Integer, Text

    class Problem(_Base):
        __tablename__ = "problems"
        id = Column(String(20), primary_key=True)
        kingdoms = Column(Text, nullable=True)

    class Submission(_Base):
        __tablename__ = "submissions"
        id = Column(String(36), primary_key=True)
        user_id = Column(String(36))
        problem_id = Column(String(20))
        status = Column(String(20))

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        db.add_all([
            Problem(id="0001", kingdoms=json.dumps([["动态规划圣殿", "🏛️"]])),
            Problem(id="0002", kingdoms=json.dumps([["字符串神殿", "🔤"]])),
            Submission(id="s1", user_id="u1", problem_id="0001", status="wrong_answer"),
            Submission(id="s2", user_id="u1", problem_id="0001", status="wrong_answer"),
            Submission(id="s3", user_id="u1", problem_id="0002", status="accepted"),
        ])
        await db.commit()

    yield factory
    await engine.dispose()


async def test_weak_kingdoms聚合未通过次数(session_factory, monkeypatch):
    monkeypatch.setattr(gt, "async_session", session_factory)
    result = await gt.get_weak_kingdoms(user_id="u1", top_n=3)
    # 动态规划圣殿 2 次未通过，应排第一；字符串神殿已 AC 不计入
    assert result["kingdoms"][0]["kingdom"] == "动态规划圣殿"
    assert result["kingdoms"][0]["failed_attempts"] == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError` 或 `AttributeError: get_weak_kingdoms`

- [ ] **Step 3: 实现 tools.py**

`backend/app/graph/tools.py`：

```python
"""
专家 Agent 工具层 — LangChain @tool 函数
工具自行开启数据库会话（无 FastAPI DI），供 ReAct Agent 调用
"""
import asyncio
import json
import logging

from langchain_core.tools import tool
from sqlalchemy import select, func, and_

from app.database import async_session
from app.models.problem import Problem
from app.models.submission import Submission
from app.services.search import semantic_search

logger = logging.getLogger(__name__)


# ============================================================
# 题目类工具（Tutor / Judge / Reviewer）
# ============================================================

@tool
async def get_problem_detail(problem_id: str) -> str:
    """获取题目详情（标题、难度、标签、题面描述）。problem_id 为 4 位题号，如 "0001"。"""
    from app.services.problems import get_problem_detail as _detail

    async with async_session() as db:
        problem = await _detail(db, problem_id)
    if not problem:
        return json.dumps({"error": f"题目 {problem_id} 不存在"}, ensure_ascii=False)
    return json.dumps({
        "id": problem.id,
        "title_cn": problem.title_cn,
        "difficulty": problem.difficulty,
        "tags": problem.tags,
        "description_cn": problem.description_cn_html[:1500],
        "hints": problem.hints[:3],
    }, ensure_ascii=False)


@tool
async def get_reference_solution(problem_id: str, language: str = "python") -> str:
    """获取题目的参考题解代码。language 可选 python/cpp/java/javascript/go。"""
    from app.services.problems import get_problem_detail as _detail

    async with async_session() as db:
        problem = await _detail(db, problem_id)
    if not problem:
        return json.dumps({"error": f"题目 {problem_id} 不存在"}, ensure_ascii=False)
    solutions = problem.solutions or {}
    code = (
        solutions.get(language)
        or solutions.get("python")
        or solutions.get("cpp")
        or solutions.get("java")
        or ""
    )
    return json.dumps({
        "problem_id": problem_id,
        "language": language,
        "reference_code": code[:4000],
    }, ensure_ascii=False)


# ============================================================
# 检索类工具（Scout / Planner）
# ============================================================

@tool
async def semantic_search_problems(query: str, top_k: int = 5) -> str:
    """用自然语言语义搜索题库，如 query="类似背包问题的动态规划入门题"。返回最匹配的题目列表。"""
    def _sync_search():
        return semantic_search(query, top_k=top_k)

    results = await asyncio.to_thread(_sync_search)
    if not results:
        return json.dumps({"results": [], "note": "没有找到相关题目"}, ensure_ascii=False)
    return json.dumps({
        "results": [
            {
                "id": r.problem.id,
                "title_cn": r.problem.title_cn,
                "difficulty": r.problem.difficulty,
                "tags": r.problem.tags[:4],
                "kingdom": r.problem.kingdom,
                "relevance": r.relevance,
            }
            for r in results
        ]
    }, ensure_ascii=False)


@tool
async def get_user_progress(user_id: str, problem_id: str = "") -> str:
    """查询用户做题进度。可传 problem_id 查当前题的尝试历史，不传则查总体统计。"""
    async with async_session() as db:
        total = await db.scalar(
            select(func.count()).select_from(Submission).where(
                Submission.user_id == user_id)
        )
        accepted = await db.scalar(
            select(func.count()).select_from(Submission).where(and_(
                Submission.user_id == user_id,
                Submission.status == "accepted",
            ))
        )
        data = {
            "total_submissions": total or 0,
            "accepted": accepted or 0,
        }
        if problem_id:
            rows = (await db.execute(
                select(Submission.status).where(and_(
                    Submission.user_id == user_id,
                    Submission.problem_id == problem_id,
                )).order_by(Submission.created_at)
            )).scalars().all()
            data["current_problem"] = {
                "problem_id": problem_id,
                "attempts": len(rows),
                "wa_count": sum(1 for s in rows if s == "wrong_answer"),
                "last_status": rows[-1] if rows else None,
            }
    return json.dumps(data, ensure_ascii=False)


# ============================================================
# 规划类工具（Planner）
# ============================================================

async def get_weak_kingdoms(user_id: str, top_n: int = 3) -> dict:
    """聚合用户未通过的王国（内部函数，@tool 包装在下方）"""
    async with async_session() as db:
        rows = (await db.execute(
            select(Problem.kingdoms, func.count())
            .join(Submission, Submission.problem_id == Problem.id)
            .where(and_(
                Submission.user_id == user_id,
                Submission.status != "accepted",
            ))
            .group_by(Problem.kingdoms)
        )).all()

    kingdom_fails: dict[str, int] = {}
    for kingdoms_json, cnt in rows:
        try:
            entries = json.loads(kingdoms_json or "[]")
        except Exception:
            continue
        for entry in entries:
            name = entry[0] if isinstance(entry, list) and entry else entry
            if isinstance(name, str):
                kingdom_fails[name] = kingdom_fails.get(name, 0) + cnt

    ranked = sorted(
        [{"kingdom": k, "failed_attempts": v} for k, v in kingdom_fails.items()],
        key=lambda x: x["failed_attempts"], reverse=True,
    )[:top_n]
    return {"kingdoms": ranked}


@tool
async def get_weak_kingdoms_tool(user_id: str, top_n: int = 3) -> str:
    """分析用户的薄弱算法王国（按未通过次数排序），供学习规划使用。"""
    return json.dumps(await get_weak_kingdoms(user_id, top_n), ensure_ascii=False)


# 供测试/其他模块直接引用的底层函数名保持不变
@tool
async def _noop() -> str:
    """占位（保证模块可被 langchain 工具序列化）"""
    return "ok"
```

> 注意：`get_weak_kingdoms` 保持为普通 async 函数（测试直接调用），对外的 LangChain 工具是 `get_weak_kingdoms_tool`。删除 `_noop` 占位工具（上面仅为说明，**不要写入文件**）。

实际写入文件时省略 `_noop`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_tools.py -v`
Expected: 1 passed

- [ ] **Step 5: 验证工具可被 Agent 绑定**

Run: `cd backend && python -c "from app.graph.tools import get_problem_detail, semantic_search_problems, get_user_progress, get_weak_kingdoms_tool, get_reference_solution; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 6: Commit**

```bash
git add backend/app/graph/tools.py backend/tests/test_tools.py
git commit -m "feat(graph): 专家 Agent 工具层（题目/检索/进度/弱点分析）"
```

---

### Task 6: Queen（Supervisor）节点

Queen 是手写节点：读 State → LLM 路由决策（JSON）→ 返回增量。循环派单，直到 `next == "finish"`。`pinned_level` 非空时（/hint 入口）直接派 tutor，跳过 LLM 路由（省钱且确定）。

**Files:**
- Create: `backend/app/graph/agents/__init__.py`
- Create: `backend/app/graph/agents/queen.py`
- Test: `backend/tests/test_queen.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_queen.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_queen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.graph.agents'`

- [ ] **Step 3: 实现 queen.py**

`backend/app/graph/agents/__init__.py`：空文件。

`backend/app/graph/agents/queen.py`：

```python
"""
精灵女王 Supervisor — 议会编排核心
职责：意图识别 → 派单（可多轮循环）→ 决定收工
路由决策由 LLM 以 JSON 输出；pinned_level 时直派 tutor（确定性路径）
"""
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.graph.llm import get_chat_model
from app.graph.state import ParliamentState, make_timeline_event
from app.graph.utils import parse_json_block

logger = logging.getLogger(__name__)

VALID_NEXT = {"scout", "tutor", "planner", "judge", "finish"}

QUEEN_SYSTEM_PROMPT = """你是「算法大陆议会」的精灵女王👑，议会调度者。

议会专家名册：
- scout 侦察兵🔭：语义搜题、查询用户进度与卡题历史
- tutor 导师🎓：三级教学帮助（hint 思路提示 / guide 部分引导 / explain 完整详解）
- planner 军师🗺️：学习规划、弱点王国分析、复盘建议
- judge 判题官⚖️：评审用户代码正确性（仅在用户明确要求判题/看代码问题时派）

你的决策规则：
1. 分析用户最新消息 + 当前状态（已有专家产出、判题结果等）
2. 用户带代码求助 → 建议先派 scout 侦察历史，再派 tutor 教学
3. 纯闲聊/简单提问 → 可直接 next=finish（由 summarize 节点回应）
4. 搜题需求 → scout；规划/复盘需求 → planner；判题需求 → judge
5. 所需专家都已产出（agent_outputs 已含足够信息）→ next=finish
6. 最多派单 3 轮，必须收敛到 finish

你必须只返回 JSON（不要 markdown 代码块）：
{
  "intent": "teaching|search|planning|judging|chat",
  "next": "scout|tutor|planner|judge|finish",
  "task_brief": "给该专家的任务说明（一句话，含关键上下文）",
  "help_level": "hint|guide|explain|null"
}
"""


def _build_route_prompt(state: ParliamentState) -> str:
    parts = [f"用户最新消息：{state['messages'][-1].content if state['messages'] else '（无）'}"]
    if state.get("problem_id"):
        parts.append(f"当前题目：{state['problem_id']}")
    if state.get("user_code"):
        parts.append(f"用户代码（截断）：{state['user_code'][:800]}")
    if state.get("agent_outputs"):
        done = "; ".join(f"{k}: {v[:200]}" for k, v in state["agent_outputs"].items())
        parts.append(f"已完成的专家产出：{done}")
    if state.get("judge_result"):
        parts.append(f"判题结果：{state['judge_result']}")
    return "\n".join(parts)


def make_queen_node(llm=None):
    """构建 Queen 节点（可注入 llm 供测试）"""
    model = llm or get_chat_model()

    async def queen_node(state: ParliamentState) -> dict:
        timeline = list(state.get("timeline") or [])

        # 确定性路径：/hint 固定级别 → 直派 tutor
        if state.get("pinned_level"):
            timeline.append(make_timeline_event(
                type="agent_start", agent="queen",
                action=f"女王受理请求，指派导师（{state['pinned_level']}）",
            ))
            return {
                "intent": "teaching",
                "current_agent": "tutor",
                "task_brief": f"用户请求 {state['pinned_level']} 级帮助",
                "timeline": timeline,
            }

        # LLM 路由决策
        messages = [
            SystemMessage(content=QUEEN_SYSTEM_PROMPT),
            HumanMessage(content=_build_route_prompt(state)),
        ]
        try:
            reply = model.invoke(messages).content
            decision = parse_json_block(reply) or {}
        except Exception as e:
            logger.error(f"Queen 路由失败，降级 finish: {e}")
            decision = {}

        nxt = decision.get("next") if decision.get("next") in VALID_NEXT else "finish"
        intent = decision.get("intent") or "chat"
        brief = decision.get("task_brief") or ""

        timeline.append(make_timeline_event(
            type="agent_start", agent="queen",
            action=f"识别意图「{intent}」，派单 {nxt}" if nxt != "finish" else "汇总收工",
        ))
        return {
            "intent": intent,
            "current_agent": nxt,
            "task_brief": brief,
            "timeline": timeline,
        }

    return queen_node
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_queen.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph/agents/ backend/tests/test_queen.py
git commit -m "feat(graph): 精灵女王 Supervisor 路由节点（LLM 决策 + 确定性降级）"
```

---

### Task 7: 专家 Agent（tutor / scout / planner）

三个开放式专家用 `create_react_agent` + 工具绑定；节点函数为闭包工厂（可注入假 Agent）。Tutor 的提示词从 `app/services/agent.py` 的 SYSTEM_PROMPT / HELP_TEMPLATES 迁移改造。

**Files:**
- Create: `backend/app/graph/agents/specialists.py`
- Test: `backend/tests/test_specialists.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_specialists.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_specialists.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 specialists.py**

`backend/app/graph/agents/specialists.py`：

```python
"""
议会专家 Agent — Tutor / Scout / Planner
每个专家 = create_react_agent（ReAct 循环 + 工具调用）+ 世界观人格提示词
节点函数记录产出与 timeline 事件；单专家失败降级不中断整体编排
"""
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from app.graph.llm import get_chat_model
from app.graph.state import ParliamentState, make_timeline_event
from app.graph.tools import (
    get_problem_detail,
    get_reference_solution,
    semantic_search_problems,
    get_user_progress,
    get_weak_kingdoms_tool,
)

# ============================================================
# 人格与职责提示词（Tutor 迁移自 app/services/agent.py）
# ============================================================

TUTOR_PROMPT = """你是「算法大陆议会」的导师🎓，来自算法大陆的可爱精灵教师！

你的性格：
- 活泼热情，擅长用生动的比喻解释抽象算法
- 鼓励用户思考，而不是直接给答案
- 说话带游戏感："勇者！""冒险者！""加油～✨"

帮助分级规则（严格遵守）：
- 【hint 提示】只给 1-2 个思路方向，不给具体解法步骤或代码，150 字内
- 【guide 引导】给核心思路 + 伪代码 + 易踩坑提醒，不给完整可运行代码，250 字左右
- 【explain 详解】完整解析：考察点、思路、参考代码（默认 Python）、复杂度分析、举例走一遍

其他规则：
- 始终用中文回复，保持精灵语气
- 可调用工具获取题目详情和参考题解（explain 级别前先看参考题解）
- 若收到侦察兵的情报（如用户 WA 历史），针对性调整提示内容
"""

SCOUT_PROMPT = """你是「算法大陆议会」的侦察兵🔭，情报专家。

职责：
- 语义搜题：调用搜索工具，用自然语言找题（如"类似背包问题的 DP 入门题"）
- 进度侦察：查询用户做题统计、当前题的尝试历史（WA 次数、最后状态）
- 输出简明情报摘要（200 字内），供女王和导师决策使用

规则：只陈述事实情报，不教学、不给解题提示。始终用中文。
"""

PLANNER_PROMPT = """你是「算法大陆议会」的军师🗺️，战略顾问。

职责：
- 调用进度/弱点工具分析用户薄弱王国
- 结合语义搜索推荐合适的练习题
- 产出学习规划：今日目标、推荐题目（带编号和难度）、复盘建议

规则：规划要具体可执行（题目用 4 位编号），语气专业带一点军师风格。始终用中文。
"""


def _build_tutor():
    return create_react_agent(
        get_chat_model(),
        tools=[get_problem_detail, get_reference_solution],
        prompt=TUTOR_PROMPT,
    )


def _build_scout():
    return create_react_agent(
        get_chat_model(),
        tools=[semantic_search_problems, get_user_progress],
        prompt=SCOUT_PROMPT,
    )


def _build_planner():
    return create_react_agent(
        get_chat_model(),
        tools=[get_user_progress, get_weak_kingdoms_tool, semantic_search_problems],
        prompt=PLANNER_PROMPT,
    )


AGENT_BUILDERS = {
    "tutor": _build_tutor,
    "scout": _build_scout,
    "planner": _build_planner,
}


def build_specialists() -> dict:
    """构建三个专家 Agent 实例 {name: agent}"""
    return {name: builder() for name, builder in AGENT_BUILDERS.items()}


def make_specialist_node(name: str, agent=None):
    """构建专家节点（可注入 agent 供测试）"""
    model_agent = agent or AGENT_BUILDERS[name]()

    async def specialist_node(state: ParliamentState) -> dict:
        timeline = list(state.get("timeline") or [])
        timeline.append(make_timeline_event(
            type="agent_start", agent=name, action="开始执行任务",
        ))
        start = time.time()

        # 组装任务指令：Queen 的派单简报 + 关键上下文
        task_parts = [f"女王派单任务：{state.get('task_brief') or '（无说明）'}"]
        if state.get("pinned_level") and name == "tutor":
            task_parts.append(f"帮助级别：【{state['pinned_level']}】（严格按此级别回复）")
        if state.get("problem_id"):
            task_parts.append(f"当前题目编号：{state['problem_id']}（可用工具查询详情）")
        if state.get("user_code"):
            task_parts.append(f"用户当前代码（可能不完整）：\n{state['user_code'][:1500]}")
        if state.get("agent_outputs"):
            others = "; ".join(
                f"[{k}] {v[:300]}" for k, v in state["agent_outputs"].items() if k != name
            )
            if others:
                task_parts.append(f"其他专家已提供的情报：{others}")
        task_parts.append(f"用户最新消息：{state['messages'][-1].content if state['messages'] else '（无）'}")

        messages = [
            SystemMessage(content="你是议会专家，请完成任务并直接给出面向用户的最终答复。"),
            HumanMessage(content="\n".join(task_parts)),
        ]

        outputs = dict(state.get("agent_outputs") or {})
        try:
            result = await model_agent.ainvoke({"messages": messages})
            reply = result["messages"][-1].content
        except Exception as e:
            # 降级：记录离线说明，不中断编排
            reply = f"（{name} 专家暂时离线：{e}）"
            timeline.append(make_timeline_event(
                type="agent_done", agent=name, action="执行失败（已降级）",
                duration_ms=int((time.time() - start) * 1000),
            ))
            outputs[name] = reply
            return {"agent_outputs": outputs, "timeline": timeline}

        timeline.append(make_timeline_event(
            type="agent_done", agent=name, action="任务完成",
            duration_ms=int((time.time() - start) * 1000),
        ))
        outputs[name] = reply
        return {"agent_outputs": outputs, "timeline": timeline}

    return specialist_node
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_specialists.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph/agents/specialists.py backend/tests/test_specialists.py
git commit -m "feat(graph): Tutor/Scout/Planner 专家 ReAct Agent 与降级策略"
```

---

### Task 8: 判题官 / 复核官 / 仲裁

判题子图三节点：Judge（迁移 `judge.py` 提示词，结构化裁决）、Reviewer（对抗视角复核）、Arbitrate（分歧仲裁）。Judge/Reviewer 用 `create_react_agent(response_format=JudgeVerdict)` 获得结构化输出；仲裁是确定性加权 + LLM 兜底。

**Files:**
- Create: `backend/app/graph/agents/judge.py`
- Test: `backend/tests/test_judge_flow.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_judge_flow.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_judge_flow.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 judge.py**

`backend/app/graph/agents/judge.py`：

```python
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
        prompt=JUDGE_PROMPT,
        response_format=JudgeVerdict,
    )


def _build_reviewer_agent():
    return create_react_agent(
        get_chat_model(),
        tools=[get_problem_detail, get_reference_solution],
        prompt=REVIEWER_PROMPT,
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_judge_flow.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph/agents/judge.py backend/tests/test_judge_flow.py
git commit -m "feat(graph): 判题官/复核官/确定性仲裁（条件触发交叉验证）"
```

---

### Task 9: 图组装 + Checkpointer

两张图共享节点：`parliament_graph`（完整议会循环）与 `judge_graph`（判题子图，供 `/progress/submit` 直调）。Summarize 节点做最终汇总（单专家产出时直通，多专家时 LLM 汇总并打 `final_reply` 标签供 token 流式）。Checkpointer 用 `AsyncSqliteSaver`（独立 SQLite 文件）。

**Files:**
- Create: `backend/app/graph/graph.py`
- Test: `backend/tests/test_graph.py`

- [ ] **Step 1: 写失败测试（注入假 LLM/Agent 的完整图流转）**

`backend/tests/test_graph.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_graph.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.graph.graph'`

- [ ] **Step 3: 实现 graph.py**

`backend/app/graph/graph.py`：

```python
"""
议会图组装 — parliament_graph（完整循环）与 judge_graph（判题子图）
- Queen 为中心：条件边路由到专家，专家回到 Queen 循环派单
- Summarize 收尾：单专家产出直通（省一次 LLM 调用），多专家 LLM 汇总
- AsyncSqliteSaver checkpointer：thread_id = user_id:problem_id 跨请求记忆
"""
import logging
import os
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.config import get_settings
from app.graph.agents.judge import (
    make_judge_node, make_reviewer_node, needs_review, resolve_verdict,
)
from app.graph.agents.queen import make_queen_node
from app.graph.agents.specialists import build_specialists, make_specialist_node
from app.graph.llm import get_chat_model
from app.graph.state import ParliamentState, make_timeline_event
from app.graph.utils import parse_json_block

logger = logging.getLogger(__name__)

MAX_DISPATCH_ROUNDS = 3  # 最多派单轮数（防死循环）

CHECKPOINT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "parliament_checkpoints.db",
)


# ============================================================
# Summarize 收尾节点
# ============================================================

SUMMARIZE_PROMPT = """你是「算法大陆议会」的精灵女王👑，现在议会专家已完成任务，请汇总给用户。

规则：
- 以女王的口吻转述专家结论，开头可用一句简短调度说明（如"我请导师看了你的代码～"）
- 保留专家答复的核心内容，不丢失技术细节
- 简洁，300 字内
直接输出给用户的内容，不要任何前后缀说明。"""


def make_summarize_node(llm=None):
    model = llm or get_chat_model(streaming=True)

    async def summarize_node(state: ParliamentState) -> dict:
        timeline = list(state.get("timeline") or [])
        outputs = state.get("agent_outputs") or {}
        user_facing = [v for k, v in outputs.items() if k in ("tutor", "planner")]

        # 直通优化：唯一面向用户的产出直接作为回复（不额外调 LLM）
        if len(user_facing) == 1:
            final_reply = user_facing[0]
        elif outputs:
            parts = "\n\n".join(f"[{k} 的答复]\n{v}" for k, v in outputs.items())
            messages = [
                SystemMessage(content=SUMMARIZE_PROMPT),
                HumanMessage(content=f"用户问题：{state['messages'][-1].content if state['messages'] else '（无）'}\n\n专家产出：\n{parts}"),
            ]
            # 打 final_reply 标签：SSE 端点按此标签做 token 级流式
            final_reply = model.with_config(tags=["final_reply"]).invoke(messages).content
        else:
            final_reply = "议会暂时没有可用的答复，请稍后再试～"

        timeline.append(make_timeline_event(type="final", agent="queen", action="汇总完成"))
        return {"final_reply": final_reply, "timeline": timeline, "current_agent": None}

    return summarize_node


# ============================================================
# 判题仲裁节点（review 完成后调用）
# ============================================================

def make_arbitrate_node():
    async def arbitrate_node(state: ParliamentState) -> dict:
        timeline = list(state.get("timeline") or [])
        final = resolve_verdict(state["judge_result"], state.get("review_verdict"))
        timeline.append(make_timeline_event(
            type="arbitrate", agent="queen",
            action="仲裁完成" + ("（采纳复核官）" if final.get("arbitrated") else "（维持原判）"),
        ))
        return {"judge_result": final, "timeline": timeline}

    return arbitrate_node


# ============================================================
# 路由函数
# ============================================================

def _route_from_queen(state: ParliamentState) -> str:
    nxt = state.get("current_agent") or "finish"
    # 防死循环：派单轮数超限时强制收工
    dispatch_rounds = sum(1 for ev in (state.get("timeline") or []) if ev.get("agent") == "queen" and ev.get("type") == "agent_start")
    if dispatch_rounds > MAX_DISPATCH_ROUNDS * 2:
        return "summarize"
    if nxt == "finish":
        return "summarize"
    return nxt if nxt in ("scout", "tutor", "planner", "judge") else "summarize"


def _route_after_judge(state: ParliamentState) -> str:
    if state.get("needs_review") and not state.get("review_verdict"):
        return "reviewer"
    return "queen"


def _route_after_reviewer(state: ParliamentState) -> str:
    jr, rv = state.get("judge_result"), state.get("review_verdict")
    if jr and rv and jr.get("correct") != rv.get("correct"):
        return "arbitrate"
    return "queen"


# ============================================================
# 图构建
# ============================================================

def build_parliament_graph(llm=None, agents: Optional[dict] = None):
    """构建完整议会图（可注入 llm/agents 供测试）"""
    queen = make_queen_node(llm=llm)
    summarize = make_summarize_node(llm=llm)
    arbitrate = make_arbitrate_node()

    if agents is None:
        agents = build_specialists()
    judge_node = make_judge_node(agent=agents.get("judge"))
    reviewer_node = make_reviewer_node(agent=agents.get("reviewer"))

    g = StateGraph(ParliamentState)
    g.add_node("queen", queen)
    g.add_node("scout", make_specialist_node("scout", agent=agents.get("scout")))
    g.add_node("tutor", make_specialist_node("tutor", agent=agents.get("tutor")))
    g.add_node("planner", make_specialist_node("planner", agent=agents.get("planner")))
    g.add_node("judge", judge_node)
    g.add_node("reviewer", reviewer_node)
    g.add_node("arbitrate", arbitrate)
    g.add_node("summarize", summarize)

    g.add_edge(START, "queen")
    g.add_conditional_edges("queen", _route_from_queen, {
        "scout": "scout", "tutor": "tutor", "planner": "planner",
        "judge": "judge", "summarize": "summarize",
    })
    for spec in ("scout", "tutor", "planner"):
        g.add_edge(spec, "queen")
    g.add_conditional_edges("judge", _route_after_judge, {"reviewer": "reviewer", "queen": "queen"})
    g.add_conditional_edges("reviewer", _route_after_reviewer, {"arbitrate": "arbitrate", "queen": "queen"})
    g.add_edge("arbitrate", "queen")
    g.add_edge("summarize", END)
    return g.compile()


def build_judge_graph(judge_agent=None, reviewer_agent=None):
    """构建判题子图：Judge → (条件) Reviewer → (条件) Arbitrate → END（供 /progress/submit 直调）"""
    g = StateGraph(ParliamentState)
    g.add_node("judge", make_judge_node(agent=judge_agent))
    g.add_node("reviewer", make_reviewer_node(agent=reviewer_agent))
    g.add_node("arbitrate", make_arbitrate_node())

    g.add_edge(START, "judge")
    g.add_conditional_edges("judge", lambda s: "reviewer" if s.get("needs_review") else END,
                            {"reviewer": "reviewer", END: END})
    g.add_conditional_edges("reviewer", _route_after_reviewer,
                            {"arbitrate": "arbitrate", END: END})
    # 一致的复核结果也要合并置信度：arbitrate 节点内 resolve_verdict 处理
    g.add_edge("arbitrate", END)
    return g.compile()


# ============================================================
# Checkpointer 单例
# ============================================================

_compiled_parliament = None
_checkpointer = None


def get_parliament_graph():
    """获取带 checkpointer 的议会图单例"""
    global _compiled_parliament, _checkpointer
    if _compiled_parliament is None:
        os.makedirs(os.path.dirname(CHECKPOINT_DB), exist_ok=True)
        _checkpointer = AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB)
        _compiled_parliament = build_parliament_graph().with_config(
            configurable={"thread_id": "default"}
        )
        # 注意：thread_id 在调用处通过 config 指定，这里仅编译
        _compiled_parliament = build_parliament_graph(checkpointer=_checkpointer)
    return _compiled_parliament


def make_thread_config(user_id, problem_id=None) -> dict:
    """构造 checkpointer thread 配置"""
    return {"configurable": {"thread_id": f"{user_id}:{problem_id or 'global'}"},
            "recursion_limit": 20}
```

> **修正说明（写入文件时应用）**：`get_parliament_graph` 中第一次赋值是笔误演示，**实际写入文件时删除中间的 `with_config` 两行**，只保留：

```python
def get_parliament_graph():
    """获取带 checkpointer 的议会图单例"""
    global _compiled_parliament, _checkpointer
    if _compiled_parliament is None:
        os.makedirs(os.path.dirname(CHECKPOINT_DB), exist_ok=True)
        _checkpointer = AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB)
        _compiled_parliament = build_parliament_graph(checkpointer=_checkpointer)
    return _compiled_parliament
```

同时 `build_parliament_graph` 签名增加 checkpointer 参数：

```python
def build_parliament_graph(llm=None, agents: Optional[dict] = None, checkpointer=None):
    ...
    return g.compile(checkpointer=checkpointer)
```

测试中 `build_parliament_graph(llm=..., agents=...)` 不传 checkpointer（无持久化，纯内存流转）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_graph.py -v`
Expected: 4 passed

- [ ] **Step 5: 验证真实图可编译（不执行 LLM）**

Run: `cd backend && python -c "from app.graph.graph import build_parliament_graph, build_judge_graph; g1 = build_parliament_graph(); g2 = build_judge_graph(); print('compiled:', type(g1).__name__, type(g2).__name__)"`
Expected: 输出 `compiled: CompiledStateGraph CompiledStateGraph`

- [ ] **Step 6: Commit**

```bash
git add backend/app/graph/graph.py backend/tests/test_graph.py
git commit -m "feat(graph): 议会图/判题子图组装 + AsyncSqliteSaver checkpointer"
```

---

### Task 10: Schema 扩展 + assistant API 改造（含 SSE）

**Files:**
- Modify: `backend/app/schemas/all.py`（AssistantResponse 扩展）
- Modify: `backend/app/api/assistant.py`（/chat 走图、新增 /chat/stream SSE、/hint 走图、/agents 名册）
- Test: `backend/tests/test_assistant_api.py`

- [ ] **Step 1: 扩展 Schema**

在 `backend/app/schemas/all.py` 的 `AssistantResponse` 中追加两个可选字段（保持向后兼容）：

```python
class AssistantResponse(BaseModel):
    """助手回复"""
    message: str
    help_level: Optional[str] = None  # hint / guide / explain / chat
    coins_spent: int = 0
    coins_remaining: int = 0
    related_problems: Optional[list[ProblemBrief]] = None
    timeline: Optional[list[dict]] = None          # 协作时间线事件流
    agents_involved: Optional[list[str]] = None    # 参与协作的 Agent id 列表
```

- [ ] **Step 2: 写失败测试（mock 图）**

`backend/tests/test_assistant_api.py`：

```python
"""assistant API 层测试（mock 议会图）"""
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class FakeUser:
    id = "u1"
    coins = 20


@pytest.fixture
def client():
    from app.main import app
    from app.services.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: FakeUser()
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
    with patch("app.api.assistant.get_parliament_graph", return_value=fake_graph), \
         patch("app.api.assistant.get_db_session"):
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


def test_chat_stream_SSE格式(client):
    fake_graph = AsyncMock()
    fake_graph.astream = AsyncMock(return_value=aiter_updates())
    with patch("app.api.assistant.get_parliament_graph", return_value=fake_graph), \
         patch("app.api.assistant.get_db_session"):
        resp = client.post("/api/assistant/chat/stream", json={
            "message": "帮我看看这题", "problem_id": "0001",
        })
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert "data:" in body and "timeline" in body


async def aiter_updates():
    """模拟 astream(stream_mode='updates') 的更新流"""
    yield {"queen": {"timeline": [{"type": "agent_start", "agent": "queen", "action": "受理", "ts": 1}]}}
    yield {"tutor": {"timeline": [{"type": "agent_done", "agent": "tutor", "action": "完成", "ts": 2}],
                     "agent_outputs": {"tutor": "答复"}}}
    yield {"summarize": {"final_reply": "最终答复", "timeline": []}}
```

> 注：`TestClient` 对 `StreamingResponse` 的 `.text` 会聚合完整响应体；`aiter_updates` 需要定义为模块级 async 生成器（如上）。若 FastAPI TestClient 同步调用 async 生成器 mock 有问题，改用 `httpx.AsyncClient(transport=ASGITransport(app=app))` + `pytest-asyncio`（在计划执行时以实际报错为准调整，保持断言不变）。

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_assistant_api.py -v`
Expected: FAIL — `/api/assistant/agents` 404 或 `timeline` 字段缺失

- [ ] **Step 4: 改造 assistant.py**

`backend/app/api/assistant.py` 全量替换为：

```python
"""
AI 助手 API — 议会多 Agent 编排入口
核心原则：图执行成功后才扣金币（事务一致性）
- POST /chat            JSON 响应（含 timeline / agents_involved，向后兼容）
- POST /chat/stream     SSE 流式（timeline 事件 + token + final）
- POST /hint            固定级别帮助（pinned_level 直通导师）
- GET  /agents          议会名册
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.assistant import AssistantMessage
from app.schemas.all import (
    AssistantRequest,
    HintRequest,
    AssistantResponse,
    ProblemBrief,
)
from app.services.auth import get_current_user
from app.services.llm import LLMNotConfiguredError, LLMServiceError
from app.services.search import semantic_search
from app.config import get_settings
from app.graph.graph import get_parliament_graph, make_thread_config
from app.graph.roster import AGENT_ROSTER

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/assistant", tags=["AI助手"])

LEVEL_COST = {
    "hint": settings.HINT_COST,
    "guide": settings.GUIDE_COST,
    "explain": settings.EXPLAIN_COST,
    "chat": 0,
}

FREE_GREETINGS = {"你好", "hello", "帮助", "help", "你是谁", "介绍一下"}


def _base_graph_input(request, user: User, pinned_level: str | None) -> dict:
    """构造图的初始 State"""
    messages = []
    if request.history:
        messages.extend(request.history[-6:])
    from langchain_core.messages import HumanMessage
    messages.append(HumanMessage(content=request.message))
    return {
        "messages": messages,
        "user_id": user.id,
        "problem_id": getattr(request, "problem_id", None),
        "user_code": (request.problem_context or {}).get("code")
            if getattr(request, "problem_context", None) else None,
        "language": (request.problem_context or {}).get("language")
            if getattr(request, "problem_context", None) else None,
        "intent": None,
        "pinned_level": pinned_level,
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


async def _settle_coins(user: User, db: AsyncSession, coins: int,
                         request, level: str, reply: str) -> None:
    """图执行成功后：扣金币 + 保存记录（一次提交保证原子性）"""
    if coins > 0:
        user.coins -= coins
    record = AssistantMessage(
        user_id=user.id,
        problem_id=getattr(request, "problem_id", None),
        role="assistant",
        content=reply,
        help_level=level,
        coins_spent=coins,
        context_snapshot=json.dumps(
            {"problem_id": getattr(request, "problem_id", None), "level": level},
            ensure_ascii=False,
        ) if getattr(request, "problem_id", None) else None,
    )
    db.add(record)
    await db.commit()


async def _related_problems(message: str, exclude_id: str | None) -> list | None:
    try:
        if message and len(message) > 10:
            results = semantic_search(message, top_k=3)
            return [r.problem for r in results if r.problem.id != exclude_id][:2]
    except Exception:
        pass
    return None


@router.post("/chat", response_model=AssistantResponse)
async def chat_with_assistant(
    request: AssistantRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """与议会自由对话（免费问候；其他消耗 1 金币）"""
    is_free = request.message.strip() in FREE_GREETINGS
    coins_to_spend = 0 if is_free else 1

    if coins_to_spend > 0 and user.coins < coins_to_spend:
        raise HTTPException(status_code=402, detail=f"金币不足！当前余额: {user.coins}💰")

    graph = get_parliament_graph()
    graph_input = _base_graph_input(request, user, pinned_level=None)
    graph_input["coins_to_spend"] = coins_to_spend

    try:
        result = await graph.ainvoke(
            graph_input, config=make_thread_config(user.id, request.problem_id)
        )
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))

    reply = result["final_reply"]
    timeline = result.get("timeline") or []
    agents_involved = list((result.get("agent_outputs") or {}).keys())

    await _settle_coins(user, db, coins_to_spend, request, "chat", reply)

    return AssistantResponse(
        message=reply,
        help_level="chat",
        coins_spent=coins_to_spend,
        coins_remaining=user.coins,
        related_problems=await _related_problems(request.message, request.problem_id),
        timeline=timeline,
        agents_involved=agents_involved,
    )


@router.post("/chat/stream")
async def chat_with_assistant_stream(
    request: AssistantRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """议会对话 SSE 流式端点

    事件格式（data: JSON\n\n）：
    - {"type": "timeline", ...}   协作时间线事件
    - {"type": "token", "content": "..."}   最终回复 token 流
    - {"type": "final", ...}      最终结构化结果（含 message/coins/timeline）
    """
    is_free = request.message.strip() in FREE_GREETINGS
    coins_to_spend = 0 if is_free else 1

    if coins_to_spend > 0 and user.coins < coins_to_spend:
        raise HTTPException(status_code=402, detail=f"金币不足！当前余额: {user.coins}💰")

    async def event_stream():
        graph = get_parliament_graph()
        graph_input = _base_graph_input(request, user, pinned_level=None)
        graph_input["coins_to_spend"] = coins_to_spend
        config = make_thread_config(user.id, request.problem_id)

        final_state = {}
        try:
            async for update in graph.astream(graph_input, config=config,
                                               stream_mode="updates"):
                for node, delta in update.items():
                    if not isinstance(delta, dict):
                        continue
                    for ev in (delta.get("timeline") or []):
                        yield f"data: {json.dumps({'type': 'timeline', **ev}, ensure_ascii=False)}\n\n"
                    if "final_reply" in delta:
                        final_state.update(delta)
            # 图执行完成 → 结算金币
            reply = final_state.get("final_reply", "")
            await _settle_coins(user, db, coins_to_spend, request, "chat", reply)
            payload = {
                "type": "final",
                "message": reply,
                "coins_spent": coins_to_spend,
                "coins_remaining": user.coins,
                "timeline": final_state.get("timeline") or [],
                "agents_involved": list((final_state.get("agent_outputs") or {}).keys()),
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except LLMNotConfiguredError as e:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)}, ensure_ascii=False)}\n\n"
        except LLMServiceError as e:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/hint", response_model=AssistantResponse)
async def get_hint(
    request: HintRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取分级帮助（hint / guide / explain），固定级别直通导师"""
    if request.level not in LEVEL_COST:
        raise HTTPException(status_code=400, detail="无效的帮助等级")

    cost = LEVEL_COST[request.level]
    if user.coins < cost:
        raise HTTPException(
            status_code=402,
            detail=f"金币不足！当前余额: {user.coins}💰，需要: {cost}💰。去闯关赚金币吧～",
        )

    graph = get_parliament_graph()
    graph_input = _base_graph_input(request, user, pinned_level=request.level)
    graph_input["coins_to_spend"] = cost

    try:
        result = await graph.ainvoke(
            graph_input, config=make_thread_config(user.id, request.problem_id)
        )
    except LLMNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))

    reply = result["final_reply"]

    await _settle_coins(user, db, cost, request, request.level, reply)

    related = None
    if request.level == "explain":
        related = await _related_problems("算法题目推荐", request.problem_id)

    return AssistantResponse(
        message=reply,
        help_level=request.level,
        coins_spent=cost,
        coins_remaining=user.coins,
        related_problems=related,
        timeline=result.get("timeline") or [],
        agents_involved=["queen", "tutor"],
    )


@router.get("/agents")
async def get_agents():
    """议会 Agent 名册（前端议会面板渲染用）"""
    return {"agents": AGENT_ROSTER}


@router.get("/history")
async def get_chat_history(
    problem_id: str | None = None,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户与AI助手的对话历史"""
    from sqlalchemy import select
    result = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.user_id == user.id)
        .order_by(AssistantMessage.created_at.desc())
        .limit(limit)
    )
    history = result.scalars().all()
    if problem_id:
        history = [m for m in history if m.problem_id == problem_id]
    return [
        {
            "id": m.id,
            "problem_id": m.problem_id,
            "role": m.role,
            "content": m.content,
            "help_level": m.help_level,
            "coins_spent": m.coins_spent,
            "created_at": m.created_at.isoformat(),
        }
        for m in reversed(history)
    ]
```

> **测试适配说明**：测试中 `patch("app.api.assistant.get_db_session")` 应改为 `patch("app.api.assistant.get_parliament_graph", ...)` + 依赖覆盖 `get_db`（提供一个能 commit 的内存 session 或 AsyncMock）。执行时若 `AssistantMessage` 写库阻塞测试，用 `app.dependency_overrides[get_db]` 注入 mock session（`commit`/`add` 为 AsyncMock）。断言保持不变。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_assistant_api.py -v`
Expected: 3 passed

- [ ] **Step 6: 手动冒烟（需 .env 配置 LLM_API_KEY）**

```bash
cd backend && uvicorn app.main:app --port 8000
# 另开终端：
curl -N -X POST http://localhost:8000/api/assistant/chat/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"message": "我是新手，该怎么开始刷题？"}'
```

Expected: 终端逐行输出 `data: {"type": "timeline", ...}`，最后一条 `data: {"type": "final", ...}`。

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/all.py backend/app/api/assistant.py backend/tests/test_assistant_api.py
git commit -m "feat(api): 议会编排接入助手 API + SSE 流式端点 + Agent 名册"
```

---

### Task 11: 判题接入议会（progress/submit）

**Files:**
- Modify: `backend/app/api/progress.py`（`_ai_evaluate` 改走判题子图）
- Test: `backend/tests/test_progress_judge.py`

- [ ] **Step 1: 写失败测试（mock 判题子图）**

`backend/tests/test_progress_judge.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_progress_judge.py -v`
Expected: FAIL — `AttributeError: module 'app.api.progress' has no attribute 'get_judge_graph'`

- [ ] **Step 3: 改造 progress.py**

在 `backend/app/api/progress.py` 中：

3a. 顶部 import 区追加：

```python
from app.graph.graph import build_judge_graph
```

3b. 在 `_ai_evaluate` 上方新增子图调用函数：

```python
# 模块级缓存：判题子图单例（无 checkpointer，判题无需跨请求记忆）
_judge_graph_instance = None


def get_judge_graph():
    """获取判题子图单例"""
    global _judge_graph_instance
    if _judge_graph_instance is None:
        _judge_graph_instance = build_judge_graph()
    return _judge_graph_instance
```

3c. 替换 `_ai_evaluate` 中"调用 ai_judge"的 try 块（原第 154-165 行附近）为走子图：

```python
    # ── 议会判题子图：Judge → (条件) Reviewer → (条件) Arbitrate ──
    graph = get_judge_graph()
    graph_input = {
        "messages": [],
        "user_id": "submit",
        "problem_id": str(problem_id),
        "user_code": code,
        "language": language,
        "intent": "judging",
        "pinned_level": None,
        "current_agent": None,
        "task_brief": "评审用户提交的代码",
        "agent_outputs": {},
        "judge_result": None,
        "review_verdict": None,
        "needs_review": False,
        "final_reply": "",
        "timeline": [],
        "coins_to_spend": 0,
    }
    try:
        result = await graph.ainvoke(graph_input)
        judge = result["judge_result"]
        correct = judge.get("correct", False)
        status = "accepted" if correct else "wrong_answer"
        result_msg = "✅ AI 判断：代码正确" if correct else "❌ AI 判断：代码存在问题"
        ai_detail = {
            "analysis": judge.get("analysis", ""),
            "issues": judge.get("issues", []),
            "suggestions": judge.get("suggestions", []),
            "comparison": judge.get("comparison", ""),
            "confidence": judge.get("confidence", 0.0),
            "execution_mode": "ai",
            "reviewed": judge.get("reviewed", False),
            "arbitrated": judge.get("arbitrated", False),
            "timeline": result.get("timeline") or [],
        }
    except Exception as e:
        logger.error(f"议会判题失败: {e}")
        ai_detail["analysis"] = f"AI 判题服务暂时不可用：{e}"
        return ("accepted", [], "AI 判题失败，默认通过", ai_detail)

    test_results = [{
        "passed": correct,
        "input": "AI 综合分析" + ("（含复核）" if ai_detail["reviewed"] else ""),
        "expected": "算法正确 + 时间复杂度合理",
        "actual": "✅ " + ai_detail["analysis"][:100] if correct
                  else "❌ " + (ai_detail["issues"][0] if ai_detail["issues"] else ai_detail["analysis"][:100]),
        "error": "",
        "runtime_ms": 0.0,
    }]
    return (status, test_results, result_msg, ai_detail)
```

> 同时删除原 `from app.services.judge import ai_judge, JudgeResult` 的局部导入与旧的 `result: JudgeResult = await ai_judge(...)` 调用块、旧 test_results 构建块（新代码已包含）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_progress_judge.py -v`
Expected: 1 passed

- [ ] **Step 5: 回归全部测试**

Run: `cd backend && python -m pytest -v`
Expected: 全部通过（此前所有任务的测试无回归）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/progress.py backend/tests/test_progress_judge.py
git commit -m "feat(api): 判题接入议会子图（条件复核 + 仲裁结果透出）"
```

---

### Task 12: 前端 — SSE 客户端 + 议会时间线面板

**Files:**
- Modify: `backend/static/api-client.js`（新增 `chatStream`）
- Modify: `quest-mode.html`（`sendAiMessage` 走 SSE、时间线渲染、CSS）

- [ ] **Step 1: api-client.js 新增流式方法**

在 `backend/static/api-client.js` 的 `assistant` 对象（约第 130 行）内、`chat` 方法后追加：

```javascript
        // SSE 流式对话 — onEvent({type: 'timeline'|'final'|'error', ...})
        async chatStream(message, problemId, onEvent) {
            const token = localStorage.getItem('token');
            const resp = await fetch(`${ApiClient.BASE_URL}/assistant/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
                },
                body: JSON.stringify({ message, problem_id: problemId }),
            });
            if (!resp.ok) {
                let detail = '请求失败';
                try { detail = (await resp.json()).detail || detail; } catch (e) {}
                throw new Error(detail);
            }
            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buf = '';
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buf += decoder.decode(value, { stream: true });
                let idx;
                while ((idx = buf.indexOf('\n\n')) >= 0) {
                    const chunk = buf.slice(0, idx);
                    buf = buf.slice(idx + 2);
                    const line = chunk.split('\n').find(l => l.startsWith('data:'));
                    if (!line) continue;
                    try { onEvent(JSON.parse(line.slice(5))); } catch (e) {}
                }
            }
        },
```

> 注意核对 `ApiClient.BASE_URL` 与 token 存储键名：打开文件确认现有 `request` 方法用的基地址与鉴权头写法，保持一致（若基地址变量名不同则相应替换）。

- [ ] **Step 2: quest-mode.html 改造 sendAiMessage**

定位 `quest-mode.html` 第 6796 行 `async function sendAiMessage()`，整体替换为：

```javascript
const AGENT_META = {
  queen:    { name: '精灵女王', emoji: '👑' },
  tutor:    { name: '导师',     emoji: '🎓' },
  judge:    { name: '判题官',   emoji: '⚖️' },
  scout:    { name: '侦察兵',   emoji: '🔭' },
  planner:  { name: '军师',     emoji: '🗺️' },
  reviewer: { name: '复核官',   emoji: '🛡️' },
};

async function sendAiMessage() {
  const input = document.getElementById('aiInput');
  const msg = input.value.trim();
  if (!msg) return;
  if (!App.isLoggedIn()) { showToast('warn', '请先登录', ''); showAuth(); return; }

  input.value = '';
  addAiMessage('user', msg);

  const pid = state.currentLevel ? String(state.currentLevel).padStart(4, '0') : null;

  // 议会时间线容器（先建占位，事件流逐个渲染）
  const body = document.getElementById('aiDialogBody');
  const tl = document.createElement('div');
  tl.className = 'agent-timeline';
  body.appendChild(tl);

  try {
    await ApiClient.assistant.chatStream(msg, pid, (ev) => {
      if (ev.type === 'timeline') {
        renderAgentTimelineEvent(tl, ev);
      } else if (ev.type === 'final') {
        addAiMessage('assistant', ev.message);
        tl.remove();
        if (ev.coins_remaining !== undefined) {
          App.user.coins = ev.coins_remaining;
          updateHUD();
        }
      } else if (ev.type === 'error') {
        addAiMessage('assistant', '⚠️ ' + (ev.detail || '议会暂时不可用'));
        tl.remove();
      }
    });
  } catch (e) {
    tl.remove();
    addAiMessage('assistant', '⚠️ ' + (e.message || '对话失败'));
  }
}

function renderAgentTimelineEvent(container, ev) {
  const meta = AGENT_META[ev.agent] || { name: ev.agent, emoji: '🤖' };
  const card = document.createElement('div');
  card.className = 'agent-tl-card' + (ev.type === 'agent_done' ? ' done' : '');
  const dur = ev.duration_ms != null ? ` · ${(ev.duration_ms / 1000).toFixed(1)}s` : '';
  card.innerHTML =
    '<span class="agent-tl-avatar">' + meta.emoji + '</span>' +
    '<span class="agent-tl-body">' +
      '<span class="agent-tl-name">' + meta.name + '</span>' +
      '<span class="agent-tl-action">' + (ev.action || '') + dur + '</span>' +
    '</span>';
  container.appendChild(card);
  const body = document.getElementById('aiDialogBody');
  body.scrollTop = body.scrollHeight;
}
```

> 检查点：`App.askAssistant` 旧调用已被替换；确认页面中无其他 `App.askAssistant` 残留引用（`Grep "askAssistant"`，仅允许定义处保留）。

- [ ] **Step 3: 追加时间线 CSS**

在 `quest-mode.html` 样式区（`.ai-msg.assistant` 规则附近，约第 1707 行后）追加：

```css
/* ═══ 议会协作时间线 ═══ */
.agent-timeline { display: flex; flex-direction: column; gap: 6px; margin: 2px 0; }
.agent-tl-card {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; border-radius: 8px;
  background: var(--card); border: 1px solid var(--border);
  font-size: 12px; color: var(--text-dim);
  animation: agentTlIn .25s ease;
}
.agent-tl-card.done { opacity: .85; }
.agent-tl-avatar { font-size: 16px; line-height: 1; }
.agent-tl-body { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.agent-tl-name { font-weight: 600; color: var(--text); font-size: 12px; }
.agent-tl-action { font-size: 11px; color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
@keyframes agentTlIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { .agent-tl-card { animation: none; } }
/* Light 主题适配 */
body.light-theme .agent-tl-card { background: #fff; border-color: #e5e7eb; }
body.light-theme .agent-tl-name { color: #1f2937; }
body.light-theme .agent-tl-action { color: #6b7280; }
```

> 检查点：确认页面 CSS 变量 `--card` / `--border` / `--text` / `--text-dim` 存在（既有主题体系已定义；深海/翠林等 6 套主题均走同一变量体系，自动适配）。

- [ ] **Step 4: 手动验收（启动后端 + 打开页面）**

```bash
cd backend && uvicorn app.main:app --port 8000
```

浏览器打开 `http://localhost:8000/`，登录后进入任意关卡 → 打开精灵面板 → 发送"我卡了，帮我看看"。

验收标准：
1. 面板中先出现"精灵女王 👑 识别意图…"时间线卡片，随后 Scout/Tutor 卡片依次淡入
2. 每张卡片带 Agent 头像、名字、动作、耗时
3. 最终回复以消息气泡呈现，时间线容器移除
4. HUD 金币按 1 扣减（非免费问候时）
5. 切换 6 套主题，时间线卡片颜色均正常

- [ ] **Step 5: Commit**

```bash
git add backend/static/api-client.js quest-mode.html
git commit -m "feat(frontend): 议会协作时间线面板 + SSE 流式客户端"
```

---

### Task 13: 端到端验收 + 版本总结文档

**Files:**
- Create: `docs/superpowers/notes/2026-08-20-multi-agent-release.md`（版本总结，遵循用户偏好：列出相比上一版本的新增内容与需人工验证清单）

- [ ] **Step 1: 全量回归**

Run: `cd backend && python -m pytest -v`
Expected: 全部通过。

- [ ] **Step 2: 端到端场景验收（手动，需 LLM_API_KEY）**

启动服务后逐项验证并记录结果：

| # | 场景 | 操作 | 预期 |
|---|------|------|------|
| 1 | 闲聊直通 | 发送"你好" | 免费；Queen 直接收工，回复精灵语气 |
| 2 | 卡题求助多专家 | 进关卡发"我卡了，帮我看看" | 时间线出现 queen→scout→tutor 链条 |
| 3 | 三级帮助 | 点 Hint/Guide/Explain 按钮 | 级别内容符合旧规则；金币 1/3/5 |
| 4 | 判题高置信度 | 提交正确代码 | 无复核；ai_feedback.reviewed=false |
| 5 | 判题触发复核 | 提交含边界 bug 代码 | 时间线含 judge→reviewer；reviewed=true |
| 6 | 判题仲裁 | 构造分歧（手工调用子图脚本） | arbitrated=true，采纳复核官 |
| 7 | 跨请求记忆 | 同题连续两轮对话 | 第二轮 Queen 感知第一轮上下文 |
| 8 | LLM 失败不扣费 | 临时改错 LLM_API_KEY 发消息 | 报错且金币不变 |
| 9 | Agent 名册 | `GET /api/assistant/agents` | 6 个 Agent 完整名册 |

- [ ] **Step 3: 写版本总结**

`docs/superpowers/notes/2026-08-20-multi-agent-release.md`：

```markdown
# vNext 版本总结 — 多 Agent 议会编排

## 相比上一版本的新增内容

1. **LangGraph 议会编排**：Supervisor（精灵女王）+ 导师/判题官/侦察兵/军师 四专家循环派单，
   新增 `backend/app/graph/` 包（state/tools/agents/graph）
2. **判题交叉验证**：判题子图条件触发复核官（置信度 < 0.7 或判错），分歧时确定性仲裁
3. **SSE 流式协作时间线**：`POST /api/assistant/chat/stream` + 前端议会面板实时渲染
4. **跨会话记忆**：AsyncSqliteSaver checkpointer（thread_id = user:problem）
5. **Agent 名册 API**：`GET /api/assistant/agents`
6. **测试体系**：pytest + pytest-asyncio，覆盖 State/路由/专家/判题/图组装/API 层

## 需人工验证清单

- [ ] 端到端 9 场景（见 docs/superpowers/plans/2026-08-20-multi-agent-parliament.md Task 13 Step 2）
- [ ] 6 套主题下议会面板视觉
- [ ] DeepSeek / OpenAI 双 LLM 后端切换
- [ ] 旧前端（ai-search-demo.html 的 ApiClient）不受 chat 接口变更影响
- [ ] 金币结算：失败不扣费、免费问候、三级计费

## 已知限制

- SSE 暂不含 token 级流式（summarize 多专家汇总路径预留 final_reply 标签，后续可开）
- 判题子图无 checkpointer（判题无跨请求记忆需求）
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/notes/2026-08-20-multi-agent-release.md
git commit -m "docs: 多 Agent 议会版本总结与验收清单"
```

---

## 自查记录（Self-Review）

1. **Spec 覆盖**：设计文档 §3 阵容 → Task 4/6/7/8；§4 State/图/checkpointer/工具 → Task 2/5/9；§5 数据流 → Task 9 测试 `test_议会图完整循环`；§6 API/SSE/前端 → Task 10/12；§7 金币/错误 → Task 10 `_settle_coins`、Task 7 降级、Task 8 仲裁；§8 测试 → 各任务 + Task 13；§9 目录 → 与计划 Files 一致。
2. **占位符**：无 TBD/TODO；Task 9 的"修正说明"与 Task 10 的"测试适配说明"是执行指引而非占位。
3. **类型一致性**：`ParliamentState` 字段在 Task 2 定义后，Task 6/7/8/9/10/11 的输入构造均逐一核对一致（含 `pinned_level`/`language`/`review_verdict`）；`make_timeline_event` 签名各任务调用一致；`build_judge_graph(judge_agent, reviewer_agent)` 与 Task 9 测试、Task 11 调用一致。
