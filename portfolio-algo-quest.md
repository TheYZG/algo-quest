## 项目定位

以 LangGraph 多 Agent 议会编排 + RAG 语义检索替代传统关键词搜索与暴力看答案，把 3,971 道 LeetCode 题做成可对话、可引导、可观测的智能刷题体验。精灵女王（Supervisor）调度 4 个专家 Agent 协作完成任务，判题环节引入双 LLM 交叉验证；游戏化王国世界观让刷题过程有叙事感，金币经济 + 三级帮助系统守护「学习循环」不被破坏。

### 核心数据

- **题库规模**：3,971 题（doocs/leetcode 数据集）
- **Agent 阵容**：Queen 调度者 + 导师/侦察兵/军师/判题官 4 专家（+ 条件触发复核官）
- **标签维度**：73 个标签 → 11 个算法王国
- **题解语言**：10+ 编程语言（Python / Java / C++ / Go / JS / ...）
- **AI 能力**：多 Agent 议会编排 · 语义搜题 · 三级帮助 · 判题交叉验证

### 技术栈

| 层          | 选型                                                       |
| ----------- | ---------------------------------------------------------- |
| Agent 编排  | LangGraph StateGraph · Supervisor 模式 · Checkpointer      |
| Agent & LLM | LangChain · DeepSeek · ReAct · 结构化输出 · SSE 流式       |
| 检索增强    | ChromaDB · shibing624/text2vec-base-chinese                |
| 后端        | FastAPI · SQLite · SQLAlchemy (async) · pytest (TDD)       |
| 前端        | 原生 HTML/JS · Canvas 王国地图 · SSE 议会时间线面板        |
| 数据工程    | Python 解析器 · 73 标签 → 11 王国映射                      |

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│  前端 quest-mode.html                                          │
│  王国地图 · 战斗刷题 · 代码编辑器 · 议会协作时间线面板           │
└───────────────┬──────────────────────────────┬────────────────┘
                │ api-client.js (JS SDK)        │ SSE 事件流
                ▼                               ▼
┌──────────────────────────────┐   ┌───────────────────────────┐
│  FastAPI 后端                 │   │  ChromaDB 向量库           │
│  /api/assistant/chat/stream  │──▶│  3971 题 embedding         │
│  /api/assistant/agents       │   │  text2vec 中文语义编码     │
│  /api/search · /progress     │   └───────────────────────────┘
└──────┬───────────────────────┘
       ▼
┌──────────────────────────────────────────────────────────────┐
│  LangGraph 议会编排（StateGraph + AsyncSqliteSaver）           │
│                                                               │
│  👑 Queen 调度者：意图识别 → JSON 结构化路由 → 循环派单         │
│      ├─ 🔭 侦察兵 scout   语义搜题 · 用户进度 · 卡题历史       │
│      ├─ 🎓 导师 tutor     Hint→Guide→Explain 三级教学          │
│      ├─ 🗺️ 军师 planner   学习规划 · 弱点王国分析              │
│      └─ ⚖️ 判题官 judge ──▶ 🛡️ 复核官 reviewer（条件触发）     │
│                              └─▶ 仲裁（分歧时确定性裁决）      │
└──────────────────────────────────────────────────────────────┘
```

> **编排机制说明**：Queen 通过 LLM JSON 结构化输出做条件路由（识别意图 → 派单专家 → 收稿判断是否继续派单或收工），派单轮数上限约束保证收敛；专家为 ReAct 模式，自主调用共享工具层（语义搜题 / 进度侦察 / 题解获取）。Checkpointer 以 `user:problem` 为 thread_id 持久化跨请求对话状态。

---

## 功能模块展示

### 模块一：多 Agent 议会编排（核心亮点）

**用户能做什么**：卡题时对精灵面板说「我卡了，帮我看看」——女王依次派出侦察兵（查你的 WA 历史与卡题记录）和导师（给出针对性帮助），协作过程以时间线卡片实时流式渲染，编排全程可观测。

**技术亮点**：LangGraph StateGraph 实现 Supervisor 模式——Queen 负责意图识别与循环派单，LLM JSON 结构化输出驱动条件路由；4 个 ReAct 专家 Agent 自主调用工具协作完成任务；AsyncSqliteSaver 持久化跨请求多轮对话记忆；SSE 逐节点推送协作事件（派单 / 执行 / 裁决 / 仲裁）。

> **📸 截图指引 `01-parliament-timeline.png`**
>
> - **在哪拍**：`quest-mode.html` → 进任意关卡 → 精灵面板输入「我卡了，帮我看看」
> - **操作**：等待议会协作完成（女王→侦察兵→导师 约 40s）
> - **画面要对齐**：议会时间线面板——女王👑派单卡片、侦察兵🔭执行卡片、导师🎓产出卡片依次展开 + 最终汇总回复
> - **证明什么**：多 Agent 编排的全程可观测性（Supervisor 循环派单 + SSE 流式推送）
> - **建议**：这是封面级截图，体现 Multi-Agent 核心亮点，优先拍好看

> **📸 截图指引 `02-agent-roster.png`**
>
> - **在哪拍**：浏览器 DevTools Network 面板，访问 `GET /api/assistant/agents`
> - **画面要对齐**：返回的 6 Agent 名册 JSON（Queen + 4 专家 + 复核官，含角色名/ emoji / 职责描述）
> - **证明什么**：Agent 名册 API + 角色职能制设计
> - **⚠️ 敏感**：无敏感信息，可直接截

---

### 模块二：判题交叉验证与仲裁

**用户能做什么**：提交代码后由判题官⚖️ 给出结构化裁决（通过/不通过 + 置信度 + 问题清单 + 改进建议）；低置信度或判错时自动触发复核官🛡️ 独立复判，两人分歧时进入确定性仲裁。

**技术亮点**：判题官基于 Pydantic 结构化输出裁决；置信度 < 0.7 或判错时条件触发复核官以对抗视角独立复判（避免双倍 LLM 成本的常态开销），分歧时确定性仲裁加权裁决——双 LLM 交叉验证替代单模型判定，降低误判率。

> **📸 截图指引 `03-judge-verdict.png`**
>
> - **在哪拍**：`quest-mode.html` → 战斗界面提交一段有 bug 的代码
> - **操作**：等待判题完成
> - **画面要对齐**：判题官裁决卡片（verdict: wrong_answer + 置信度 + 问题清单 + 改进建议），若触发复核则展示复核官卡片与仲裁结果
> - **证明什么**：LLM 结构化判题 + 条件触发交叉验证的完整链路
> - **备注**：判错 + 低置信度的提交更容易同时展示「判题官→复核官→仲裁」三张卡片，是最佳素材

---

### 模块三：AI 语义搜索

**用户能做什么**：用自然语言搜题，如「类似背包问题的 DP 题目」「双指针解法的字符串题」，不再依赖标签关键词匹配。语义搜索同时作为侦察兵专家的工具层，为议会协作提供情报。

**技术亮点**：ChromaDB 向量检索 + `shibing624/text2vec-base-chinese` 中文语义模型（768 维），覆盖 3,971 题与 73 标签维度，Top-5 召回精度约 87%。

> **📸 截图指引 `04-semantic-search-input.png`**
>
> - **在哪拍**：`ai-search-demo.html` 或 `quest-mode.html` 的搜索入口
> - **操作**：输入「类似背包问题的 DP 题目」
> - **画面要对齐**：搜索框 + 输入的自然语言查询语句
> - **证明什么**：自然语言查询能力（非关键词匹配）

> **📸 截图指引 `05-semantic-search-result.png`**
>
> - **在哪拍**：同上，点击搜索后
> - **画面要对齐**：返回的题目列表（标题 + 相似度分数 + 所属王国标签），能看到「完全背包」「0-1 背包」等相关题目排在前列
> - **证明什么**：RAG 召回结果的相关性，向量相似度排序

---

### 模块四：三级帮助系统（导师专家）

**用户能做什么**：卡题时按需请求 Hint（方向）/ Guide（步骤）/ Explain（详解）三个层级的帮助，导师专家根据解题状态与侦察兵情报自主选择帮助层级。

**技术亮点**：按信息揭示量设计的递进策略——Hint 仅给方向、Guide 拆解步骤、Explain 展示思路，避免直接给答案破坏刷题学习循环。金币成本递增（1/3/5 金币）守护使用克制；Queen 结合侦察兵情报（用户 WA 历史、卡题记录）自适应调度帮助层级。

> **📸 截图指引 `06-agent-hint.png`**
>
> - **在哪拍**：`quest-mode.html` → 进任意关卡战斗界面 → 点开「算法精灵」面板
> - **操作**：点 Hint 按钮
> - **画面要对齐**：精灵角色对话框 + 1-2 句方向性提示（不给具体解法）+ HUD 金币 -1
> - **证明什么**：分级帮助的「最小信息揭示」设计 + Prompt 约束 LLM 不越界

> **📸 截图指引 `07-agent-guide.png`**
>
> - **在哪拍**：同上
> - **操作**：点 Guide 按钮
> - **画面要对齐**：核心思路 + 伪代码片段（非完整可运行代码）+ 易踩坑提醒 + 金币 -3
> - **证明什么**：中间层级的「思路 + 伪代码」边界控制

> **📸 截图指引 `08-agent-explain.png`**
>
> - **在哪拍**：同上
> - **操作**：点 Explain 按钮
> - **画面要对齐**：完整解题分析（考察点 + 思路 + 参考代码 + 复杂度分析）+ 金币 -5
> - **证明什么**：详解模式的完整结构化输出，Pydantic 校验格式

---

### 模块五：数据工程与多语言题解

**用户能做什么**：在代码编辑器切换 5 种语言模板（Python/Java/C++/Go/JS），查看多语言参考题解。

**技术亮点**：解析 doocs/leetcode 多语言题解库，结构化提取题目描述 / 代码模板 / 参考解答，建立 73 标签到 11 算法王国的全量映射，为语义搜索与专家 Agent 推理提供统一数据底座。

> **📸 截图指引 `09-multi-language-solutions.png`**
>
> - **在哪拍**：`quest-mode.html` → 进任意关卡 → 代码编辑器语言下拉
> - **操作**：切换 Python → Java → C++，展示同一题的 3 种语言模板
> - **画面要对齐**：语言选择器 + 3 段不同语言的代码模板（可拼接或三连图）
> - **证明什么**：多语言题解库的结构化提取能力

> **📸 截图指引 `10-data-import-log.png`**
>
> - **在哪拍**：终端运行导入脚本 `python -m app.services.importer`
> - **画面要对齐**：终端输出显示「导入 N 题」「映射到 11 王国」「ChromaDB 写入 N 条 embedding」
> - **证明什么**：数据工程闭环（解析 → 结构化 → 标签映射 → 向量化入库）
> - **⚠️ 敏感**：本地路径打码；若导入脚本跑不起来，改截 DB 查询 `SELECT COUNT(*) FROM problems` 的结果

---

### 模块六：游戏化王国世界观

**用户能做什么**：在「算法大陆」地图上选择 11 个算法王国（数据结构工坊 / 动态规划圣殿 / 字符串神殿 ...）+ 混沌领域，关卡顺序解锁。

**技术亮点**：每题多王国归属（kingdoms JSON 数组），73 标签到 11 王国的全量映射，前端纯 Canvas/SVG 绘制地图，后端 API 实时下发王国视觉属性。

> **📸 截图指引 `11-kingdom-map.png`**
>
> - **在哪拍**：`quest-mode.html` → 主线征程模式入口
> - **画面要对齐**：算法大陆全貌（11 王国 + 混沌领域）+ 各王国视觉差异化（颜色 / 图标）+ 部分王国显示已通关进度
> - **证明什么**：游戏化世界观设计 + 王国体系的全量映射

---

### 模块七：金币经济系统

**用户能做什么**：AC 题目赚取金币（Easy +5 / Medium +10 / Hard +20），请求 Agent 帮助消耗金币（Hint -1 / Guide -3 / Explain -5，普通对话 -1）。

**技术亮点**：金币双向流动设计，LLM 调用成功后才扣金币（事务一致性），避免调用失败仍扣费的边界问题；多 Agent 协作按次结算，编排轮数不影响单次计费。

> **📸 截图指引 `12-coin-hud-cost.png`**
>
> - **在哪拍**：`quest-mode.html` → 进任意关卡战斗界面
> - **操作**：点开「算法精灵」帮助面板，让 Hint / Guide / Explain 三个按钮都显示
> - **画面要对齐**：左上 HUD 金币数字（如 `💰 20`）+ 三个帮助按钮的消耗标注（`Hint -1` / `Guide -3` / `Explain -5`）同框
> - **证明什么**：分级帮助的成本设计 + 金币 HUD 实时显示

> **📸 截图指引 `13-coin-reward-deduct.png`**
>
> - **在哪拍**：同上战斗界面
> - **操作**：先点 Hint（金币 20→19），再 AC 一道题（金币 19+5=24）
> - **画面要对齐**：`💸 -1` 扣费 toast + `🎉 VICTORY! +5💰` 奖励 toast
> - **证明什么**：金币双向流动 + 事务一致性（LLM 成功才扣费）
> - **备注**：两步 toast 不好同框就分 `13a-coin-deduct.png` + `13b-coin-reward.png` 拼接

---

### 模块八：进度追踪

**用户能做什么**：查看王国通关进度（已通关 X/Y）、关卡解锁状态、历史提交记录（AC / WA / TLE 状态）。提交历史同时作为侦察兵专家的情报源。

**技术亮点**：关卡顺序解锁机制 + 进度持久化（SQLite Submission 表），提交状态机覆盖 accepted / wrong_answer / timeout / runtime_error / compile_error。

> **📸 截图指引 `14-kingdom-progress.png`**
>
> - **在哪拍**：`quest-mode.html` → 主线征程 → 选一个有进度数据的王国
> - **操作**：先随便 AC 2-3 道题制造进度，再回到王国关卡列表
> - **画面要对齐**：王国顶部冒险进度条（「已通关 3/25」）+ 下方关卡列表的 defeated（灰掉/打勾）与 locked（锁住）两种状态同框
> - **证明什么**：关卡顺序解锁机制 + 进度持久化

> **📸 截图指引 `15-submission-history.png`**
>
> - **在哪拍**：浏览器 DevTools Network 面板，访问 `/api/progress/submissions`；或前端若有提交记录页就直接截
> - **画面要对齐**：返回 JSON 里能看到 `problem_id / status / submitted_at / coins_earned` 字段，最好有 accepted + wrong_answer 两种状态
> - **证明什么**：提交记录持久化 + 状态机
> - **⚠️ 敏感**：`user_id` 等字段打码

---

## 截图拍摄指引汇总

| 序号 | 文件名                            | 模块              | 去哪截                            | 优先级 |
| ---- | --------------------------------- | ----------------- | --------------------------------- | ------ |
| 01   | `01-parliament-timeline.png`      | 多 Agent 议会编排 | `quest-mode.html` 精灵面板求助    | ⭐⭐⭐    |
| 02   | `02-agent-roster.png`             | 多 Agent 议会编排 | DevTools / `GET /api/assistant/agents` | ⭐⭐ |
| 03   | `03-judge-verdict.png`            | 判题交叉验证      | `quest-mode.html` 提交带 bug 代码 | ⭐⭐⭐    |
| 04   | `04-semantic-search-input.png`    | AI 语义搜索       | `ai-search-demo.html` 搜索框      | ⭐⭐⭐    |
| 05   | `05-semantic-search-result.png`   | AI 语义搜索       | 同上，搜索结果列表                | ⭐⭐⭐    |
| 06   | `06-agent-hint.png`               | 三级帮助系统      | `quest-mode.html` 战斗界面 → Hint | ⭐⭐⭐    |
| 07   | `07-agent-guide.png`              | 三级帮助系统      | 同上 → Guide                      | ⭐⭐⭐    |
| 08   | `08-agent-explain.png`            | 三级帮助系统      | 同上 → Explain                    | ⭐⭐⭐    |
| 09   | `09-multi-language-solutions.png` | 数据工程          | `quest-mode.html` 代码编辑器      | ⭐⭐     |
| 10   | `10-data-import-log.png`          | 数据工程          | 终端运行导入脚本                  | ⭐⭐     |
| 11   | `11-kingdom-map.png`              | 游戏化世界观      | `quest-mode.html` 主线征程入口    | ⭐⭐⭐    |
| 12   | `12-coin-hud-cost.png`            | 金币经济          | `quest-mode.html` 战斗界面 HUD    | ⭐⭐     |
| 13   | `13-coin-reward-deduct.png`       | 金币经济          | 同上，扣费 + 奖励 toast           | ⭐⭐     |
| 14   | `14-kingdom-progress.png`         | 进度追踪          | `quest-mode.html` 王国关卡列表    | ⭐⭐     |
| 15   | `15-submission-history.png`       | 进度追踪          | DevTools Network / 提交记录页     | ⭐⭐     |

### 推荐拍摄顺序（按依赖关系，避免反复切界面）

1. **`11-kingdom-map.png`** — 进主线征程先截封面
2. **`14-kingdom-progress.png`** — 选个王国，AC 2-3 题制造进度后截
3. **`13b-coin-reward.png`** — 刚才 AC 的题会弹 +💰 toast，顺手截
4. **`03-judge-verdict.png`** — 提交一段带 bug 的代码，截判题官（+复核/仲裁）裁决卡片
5. **`01-parliament-timeline.png`** — 精灵面板输入「我卡了」，等议会协作完整跑完（约 40s），截时间线全貌
6. **`12-coin-hud-cost.png`** — HUD + 帮助按钮同框
7. **`06/07/08-agent-*.png`** — 同一界面连点 Hint/Guide/Explain 截三张
8. **`13a-coin-deduct.png`** — 点 Hint 触发扣费 toast
9. **`09-multi-language-solutions.png`** — 代码编辑器切语言
10. **`04/05-semantic-search-*.png`** — 切到 `ai-search-demo.html` 搜题
11. **`02-agent-roster.png`** — DevTools 访问 agents API
12. **`10-data-import-log.png`** — 最后跑终端命令截日志
13. **`15-submission-history.png`** — 这时候提交记录够多了，截 Network

### 敏感信息打码清单

| 截图                        | 需打码内容                              |
| --------------------------- | --------------------------------------- |
| `10-data-import-log.png`    | 本地文件路径（如 `C:/Users/21349/...`） |
| `15-submission-history.png` | `user_id` / `user_email` 字段           |
| 所有含终端/DevTools 的截图  | DeepSeek API key（若出现）              |

---

## 建议省略的截图（附理由）

> **建议省略：真实代码评测控制台**
> 沙箱执行系统已于 2026-07-01 禁用，全部改为 AI 大模型判题（`overview.md` 有记录）。若截图展示「测试用例逐条 pass/fail」会与当前实现不符，且与简历「AI Agent」主线冲突。

> **建议省略：登录注册页**
> 支撑性功能，无 AI 技术说服力，占篇幅不增值。

> **建议省略：多套前端风格切换**
> 早期探索产物（暗色IDE/亮色学术/赛博朋克），会削弱「AI Agent 平台」的主线叙事。若想展示设计能力，放一张 `11-kingdom-map.png` 足矣。

---

## 项目结构速览

```
algo-quest/
├── quest-mode.html          # 主程序（王国地图 + 战斗刷题 + 议会时间线面板）
├── ai-search-demo.html      # AI 语义搜索演示页
├── index.html               # 风格对比导航页
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI 路由（search/assistant/progress/problems/auth）
│   │   ├── graph/           # LangGraph 议会编排（state/queen/agents/judge/图组装）
│   │   ├── services/        # 核心服务（agent/search/llm/embedding/importer）
│   │   ├── models/          # SQLAlchemy 模型（User/Problem/Submission/AssistantMessage）
│   │   └── schemas/         # Pydantic 响应模型
│   ├── tests/               # pytest 测试（34 例：状态/路由/专家/判题/图组装/API）
│   └── static/              # api-client.js + integration.js（前后端桥梁）
├── solution/                # doocs/leetcode 数据集（3971 题）
└── docs/                    # 文档（设计稿 / 实施计划 / 发布总结）
```

---

## 简历原文依据

> 本文档的截图清单严格对应简历项目经历「多 Agent 议会编排的智能刷题平台」三大亮点：
>
> 1. **多 Agent 议会编排 + 流式协作与 Memory** → 模块一（截图 01-02）+ 模块四（截图 06-08）
> 2. **判题交叉验证与仲裁** → 模块二（截图 03）
> 3. **检索底座（语义搜索 + 数据工程）** → 模块三（截图 04-05）+ 模块五（截图 09-10）
>
> 模块六/七/八为视觉记忆点与系统完整性补充，不与简历冲突。
