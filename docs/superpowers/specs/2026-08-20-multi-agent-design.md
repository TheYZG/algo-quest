# 多 Agent 编排系统设计：「算法大陆议会」

> 日期：2026-08-20
> 状态：设计定稿（待实现）
> 动机：将现有单次 LLM 调用的"伪 Agent"升级为 LangGraph 驱动的多 Agent 编排系统，作为简历/面试的核心技术亮点

## 1. 背景与目标

### 现状问题

- `backend/app/services/agent.py` 只是提示词模板库（hint/guide/explain/chat），每次请求单次调用 LLM 即返回，无自主决策
- `backend/app/services/judge.py` AI 判题同样是单次调用
- 无工具调用（function calling）、无 Agent 间协作、无编排循环

### 目标

- 用 LangGraph 构建 **Supervisor 编排 + 专家 Agent 协作** 架构，全量接管现有 AI 能力（求助/判题/搜题/对话/规划）
- 判题引入**条件触发的交叉验证**，降低单 LLM 误判率
- 前端实时展示 **Agent 协作时间线**（SSE 流式），强化演示效果
- 保持金币经济与现有 API 的向后兼容

## 2. 架构总览

```
用户请求（求助 · 判题 · 搜题 · 规划）
        │
        ▼
┌─ LangGraph 编排层 ────────────────────────────┐
│  精灵女王 Supervisor（意图识别·编排·仲裁）        │
│     │ 派单（循环，可多轮）                        │
│  ┌───────┬────────┬────────┬────────┐          │
│  导师     判题官    侦察兵    军师                 │
│  Tutor   Judge    Scout    Planner              │
│            │ 低置信度触发                         │
│         复核官 Reviewer                          │
└────────────────┬───────────────────────────────┘
                 │ 工具调用
┌─ 工具与数据层 ──────────────────────────────────┐
│  DeepSeek LLM  │ ChromaDB 向量库 │ SQLite 状态库 │
└────────────────────────────────────────────────┘
        │
        ▼
SSE 协作时间线 + 最终回复 → 前端议会面板
```

## 3. Agent 阵容与职责

| Agent | 世界观角色 | 职责（接管现有功能） | 专属工具 | 实现方式 |
|---|---|---|---|---|
| Supervisor | 精灵女王 | 意图识别、任务拆解、路由调度、汇总仲裁、金币结算触发 | 路由决策（结构化输出） | 手写 LangGraph 节点 |
| Tutor | 导师 | 三级帮助 hint/guide/explain（改造自 agent.py） | 题目详情、参考题解 | create_react_agent + 工具 |
| Judge | 判题官 | AI 判题（改造自 judge.py） | 题目详情、参考题解 | create_react_agent + 工具 |
| Scout | 侦察兵 | 语义搜题 + 用户进度侦察 | ChromaDB 搜索、进度查询 | create_react_agent + 工具 |
| Planner | 军师 | 学习规划、弱点分析、复盘建议 | 进度查询、弱点王国分析、搜题 | create_react_agent + 工具 |
| Reviewer | 复核官 | 判题二次验证（对抗视角 prompt） | 同 Judge | create_react_agent + 工具 |

> 常驻阵容为 5 Agent（Queen + 4 专家）；Reviewer 是判题子图内条件触发的第 6 角色，不计入常驻阵容。

## 4. LangGraph 核心设计

### 4.1 State 定义

```python
class ParliamentState(TypedDict):
    messages: Annotated[list, add_messages]   # 对话记忆
    user_id: int
    problem_id: str | None
    user_code: str | None
    intent: str | None                        # Queen 识别的意图
    current_agent: str | None                 # 当前该谁执行
    agent_outputs: dict[str, str]             # 各专家产出
    judge_result: dict | None                 # 判题结构化结果
    needs_review: bool                        # 是否触发复核
    final_reply: str                          # 汇总回复
    timeline: list[dict]                      # 协作事件流（前端展示）
    coins_to_spend: int                       # 结算金额
```

### 4.2 图结构

- **Supervisor 为中心节点**：分析 State → 输出路由决策（派哪个专家、带什么任务上下文）
- **循环编排**：专家执行完回到 Queen，Queen 决定"继续派单 or 汇总收工"（非单次流水线）
- **条件边**：
  - 求助场景：Queen 可先派 Scout 侦察再派 Tutor 教学（串行多 Agent）
  - 判题场景：Judge → `confidence < 0.7 或判定错误` → Reviewer → 分歧时 Queen 仲裁
- **判题子图**：Judge/Reviewer/仲裁封装为子图，供 `progress/submit` 复用

### 4.3 Checkpointer（跨会话记忆）

- `SqliteSaver` 复用 SQLite（独立文件，避免与业务库耦合）
- `thread_id = f"{user_id}:{problem_id}"`
- 实现跨请求对话记忆与断点恢复

### 4.4 工具注册（tools.py）

| 工具 | 提供给 | 底层 |
|---|---|---|
| `semantic_search(query, top_k)` | Scout / Planner | 现有 search.py（需包一层 async） |
| `get_user_progress(user_id)` | Scout / Planner | 查 Submission 表 |
| `get_weak_kingdoms(user_id)` | Planner | 进度聚合分析 |
| `get_problem_detail(problem_id)` | Tutor / Judge / Reviewer | 现有 problems.py |
| `get_reference_solution(problem_id, lang)` | Tutor / Judge / Reviewer | 现有题解库 |

## 5. 场景数据流示例（卡题求助）

```
用户："我卡了，帮我看看" + 当前代码
  → Queen 识别意图=教学辅导，且发现带代码 → 先派 Scout
  → Scout 查进度："该用户在此题已 WA 2 次，倾向暴力解法"
  → Queen 把 Scout 情报塞进 Tutor 的任务上下文
  → Tutor 生成针对性 hint（结合 WA 历史提示复杂度问题）
  → Queen 汇总回复 + 返回 timeline（全程 SSE 推送）
```

## 6. API 与前端改造

### 6.1 后端 API（向后兼容）

- `POST /api/assistant/chat` → 内部改 `graph.astream()`
  - **SSE 事件**：`agent_start`（Agent 开始）/ `agent_done`（Agent 完成）/ `token`（流式文本）/ `final`（最终结构化结果）
  - 响应保留原字段，新增 `timeline`、`agents_involved`
- `POST /api/progress/submit` → 判题走 Judge 子图（条件复核）
- `GET /api/assistant/agents`（新增）→ Agent 名册（头像、名字、职责介绍）

### 6.2 前端（quest-mode.html）

- 精灵面板 → **议会面板**：时间线卡片流（Agent 头像 + 名字 + 动作 + 耗时）
- SSE 逐事件渲染动画
- 6 套主题适配（暗夜/晨曦/深海/翠林/紫晶/余晖）

## 7. 金币经济与错误处理

### 7.1 金币计费（不变）

- hint 1 / guide 3 / explain 5 / chat 0-1，**多 Agent 编排对用户不加价**，复核免费
- 保持"LLM 调用成功后才扣金币"的事务一致性原则（图执行成功后统一结算）

### 7.2 错误处理

- LLM 未配置/调用失败 → 图终止 → 402/502，不扣金币
- 单个专家失败 → Queen 降级：跳过该专家并在回复中说明，不中断整体
- 复核分歧 → Queen 仲裁节点取加权结论（Reviewer 为对抗视角，可信度略高）

## 8. 测试策略

- **单测**：路由决策正确性（mock LLM 返回结构化路由）、State 流转、金币结算边界（免费问候/余额不足）
- **集成**：四场景端到端（求助/判题/搜题/规划）+ 复核触发路径 + checkpointer 断点续聊
- **演示验收**：时间线可见、低置信度判题能触发复核、跨请求记忆生效

## 9. 目录结构

```
backend/app/graph/
├── state.py          # ParliamentState 定义
├── agents/           # queen.py / tutor.py / judge.py / scout.py / planner.py / reviewer.py
├── tools.py          # 工具注册（搜题/进度/题目详情/弱点分析）
└── graph.py          # 图组装 + checkpointer
```

- 现有 `agent.py` / `judge.py` 的 prompt 资产迁移进对应专家模块
- `assistant.py` / `progress.py` 改为调用图，原模板函数保留过渡期后移除
- `requirements.txt` 新增：`langgraph`、`langchain-core`、`langchain-openai`

## 10. 简历故事线

> 基于 LangGraph 构建 Supervisor 编排的 5-Agent 协作系统：意图路由 + 循环派单调度、判题低置信度条件触发双 Agent 交叉验证（降低 LLM 误判率）、SSE 流式推送 Agent 协作时间线、SqliteSaver 实现跨会话记忆与断点恢复。

面试可展开的深挖点：为什么选 Supervisor 模式而非 P2P 协作（可控性/成本/调试）、条件复核的成本权衡、编排循环的终止条件设计、金币结算与图执行的事务一致性。

## 11. 明确不做（YAGNI）

- 不做 11 王国人格化 Agent（提示词维护成本高，收益低）
- 不做双 Agent 并行判题（延迟/成本翻倍，条件复核已覆盖）
- 不做 Agent 间自由对话（P2P）模式
- 不引入消息队列/分布式编排（单机 FastAPI 足够）
