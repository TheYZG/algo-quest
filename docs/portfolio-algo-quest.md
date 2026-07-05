> 没有omaDB  

---

## 项目定位

以 RAG 语义检索 + Agent 分级帮助替代传统关键词搜索与暴力看答案，把 3,971 道 LeetCode 题做成可对话、可引导、可追踪的智能刷题体验。游戏化王国世界观让刷题过程有叙事感,金币经济 + 三级帮助系统守护「学习循环」不被破坏。

### 核心数据

- **题库规模**：3,971 题（doocs/leetcode 数据集）
- **标签维度**：73 个标签 → 11 个算法王国
- **题解语言**：10+ 编程语言（Python / Java / C++ / Go / JS / ...）
- **AI 能力**：语义搜题 · 三级 Agent 帮助 · LLM 判题

### 技术栈

| 层          | 选型                                        |
| ----------- | ------------------------------------------- |
| Agent & LLM | LangChain · DeepSeek · Prompt Engineering   |
| 检索增强    | ChromaDB · shibing624/text2vec-base-chinese |
| 后端        | FastAPI · SQLite · SQLAlchemy (async)       |
| 前端        | 原生 HTML/JS · Canvas 王国地图 · 6 套主题   |
| 数据工程    | Python 解析器 · 73 标签 → 11 王国映射       |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│  前端 quest-mode.html                                    │
│  王国地图 · 战斗刷题 · 代码编辑器 · 算法精灵面板            │
└───────────────┬─────────────────────────┬───────────────┘
                │ api-client.js (JS SDK)   │
                ▼                          ▼
┌──────────────────────┐   ┌──────────────────────────────┐
│  FastAPI 后端         │   │  ChromaDB 向量库              │
│  /api/search          │──▶│  3971 题 embedding            │
│  /api/assistant       │   │  sentence-transformers 编码   │
│  /api/progress        │   └──────────────────────────────┘
│  /api/problems        │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  LangChain Agent     │
│  Hint / Guide /      │
│  Explain 三级帮助     │
│  DeepSeek LLM        │
└──────────────────────┘
```

> **向量模型说明**：使用 `shibing624/text2vec-base-chinese`（中文语义模型，768 维），通过 sentence-transformers 库加载。针对中文题面与算法术语做了语义对齐优化。

---

## 功能模块展示

### 模块一：AI 语义搜索

**用户能做什么**：用自然语言搜题，如「类似背包问题的 DP 题目」「双指针解法的字符串题」,不再依赖标签关键词匹配。

**技术亮点**：ChromaDB 向量检索 + `shibing624/text2vec-base-chinese` 中文语义模型（768 维）,覆盖 3,971 题与 73 标签维度。

> !![image-20260705154839268](C:\Users\21349\AppData\Roaming\Typora\typora-user-images\image-20260705154839268.png)
>
> **📸 截图指引 `01-semantic-search-input.png`**
>
> - **在哪拍**：`ai-search-demo.html` 或 `quest-mode.html` 的搜索入口
> - **操作**：输入「类似背包问题的 DP 题目」
> - **画面要对齐**：搜索框 + 输入的自然语言查询语句
> - **证明什么**：自然语言查询能力（非关键词匹配）

> ![image-20260705154924404](C:\Users\21349\AppData\Roaming\Typora\typora-user-images\image-20260705154924404.png)
>
> **📸 截图指引 `02-semantic-search-result.png`**
>
> - **在哪拍**：同上,点击搜索后
> - **画面要对齐**：返回的题目列表（标题 + 相似度分数 + 所属王国标签）,能看到「完全背包」「0-1 背包」等相关题目排在前列
> - **证明什么**：RAG 召回结果的相关性,向量相似度排序

---

### 模块二：三级 Agent 帮助系统

**用户能做什么**：卡题时按需请求 Hint（方向）/ Guide（步骤）/ Explain（详解）三个层级的帮助,Agent 根据解题状态自主选择帮助层级。

**技术亮点**：按信息揭示量设计的递进策略——Hint 仅给方向、Guide 拆解步骤、Explain 展示思路,避免直接给答案破坏刷题学习循环。金币成本递增（1/3/5 金币）守护使用克制。

> ![image-20260705154958171](C:\Users\21349\AppData\Roaming\Typora\typora-user-images\image-20260705154958171.png)
>
> **📸 截图指引 `03-agent-hint.png`**
>
> - **在哪拍**：`quest-mode.html` → 进任意关卡战斗界面 → 点开「算法精灵」面板
> - **操作**：点 Hint 按钮
> - **画面要对齐**：精灵角色对话框 + 1-2 句方向性提示（不给具体解法）+ HUD 金币 -1
> - **证明什么**：分级帮助的「最小信息揭示」设计 + Prompt 约束 LLM 不越界

> ![image-20260705155030960](C:\Users\21349\AppData\Roaming\Typora\typora-user-images\image-20260705155030960.png)
>
> **📸 截图指引 `04-agent-guide.png`**
>
> - **在哪拍**：同上
> - **操作**：点 Guide 按钮
> - **画面要对齐**：核心思路 + 伪代码片段（非完整可运行代码）+ 易踩坑提醒 + 金币 -3
> - **证明什么**：中间层级的「思路 + 伪代码」边界控制

> ![image-20260705155149170](C:\Users\21349\AppData\Roaming\Typora\typora-user-images\image-20260705155149170.png)
>
> **📸 截图指引 `05-agent-explain.png`**
>
> - **在哪拍**：同上
> - **操作**：点 Explain 按钮
> - **画面要对齐**：完整解题分析（考察点 + 思路 + 参考代码 + 复杂度分析）+ 金币 -5
> - **证明什么**：详解模式的完整结构化输出,Pydantic 校验格式

---

### 模块三：数据工程与多语言题解

**用户能做什么**：在代码编辑器切换 5 种语言模板（Python/Java/C++/Go/JS）,查看多语言参考题解。

**技术亮点**：解析 doocs/leetcode 多语言题解库,结构化提取题目描述 / 代码模板 / 参考解答,建立 73 标签到 11 算法王国的全量映射,为语义搜索与 Agent 帮助提供数据基础。

> ![image-20260705155245041](C:\Users\21349\AppData\Roaming\Typora\typora-user-images\image-20260705155245041.png)
>
> **📸 截图指引 `06-multi-language-solutions.png`**
>
> - **在哪拍**：`quest-mode.html` → 进任意关卡 → 代码编辑器语言下拉
> - **操作**：切换 Python → Java → C++,展示同一题的 3 种语言模板
> - **画面要对齐**：语言选择器 + 3 段不同语言的代码模板（可拼接或三连图）
> - **证明什么**：多语言题解库的结构化提取能力

> 没有截图，前端自由发挥
>
> **📸 截图指引 `07-data-import-log.png`**
>
> - **在哪拍**：终端运行导入脚本 `python -m app.services.importer`
> - **画面要对齐**：终端输出显示「导入 N 题」「映射到 11 王国」「ChromaDB 写入 N 条 embedding」
> - **证明什么**：数据工程闭环（解析 → 结构化 → 标签映射 → 向量化入库）
> - **⚠️ 敏感**：本地路径打码；若导入脚本跑不起来,改截 DB 查询 `SELECT COUNT(*) FROM problems` 的结果

---

### 模块四：游戏化王国世界观

**用户能做什么**：在「算法大陆」地图上选择 11 个算法王国（数据结构工坊 / 动态规划圣殿 / 字符串神殿 ...）+ 混沌领域,关卡顺序解锁。

**技术亮点**：每题多王国归属（kingdoms JSON 数组）,73 标签到 11 王国的全量映射,前端纯 Canvas/SVG 绘制地图,后端 API 实时下发王国视觉属性。

> ![image-20260705155754882](C:\Users\21349\AppData\Roaming\Typora\typora-user-images\image-20260705155754882.png)
>
> **📸 截图指引 `08-kingdom-map.png`**
>
> - **在哪拍**：`quest-mode.html` → 主线征程模式入口
> - **画面要对齐**：算法大陆全貌（11 王国 + 混沌领域）+ 各王国视觉差异化（颜色 / 图标）+ 部分王国显示已通关进度
> - **证明什么**：游戏化世界观设计 + 王国体系的全量映射
> - **建议**：这是封面级截图,优先拍好看

---

### 模块五：金币经济系统

**用户能做什么**：AC 题目赚取金币（Easy +5 / Medium +10 / Hard +20）,请求 Agent 帮助消耗金币（Hint -1 / Guide -3 / Explain -5）。

**技术亮点**：金币双向流动设计,LLM 调用成功后才扣金币（事务一致性）,避免调用失败仍扣费的边界问题。

> 没有截图，前端自由发挥
>
> **📸 截图指引 `09-coin-hud-cost.png`**
>
> - **在哪拍**：`quest-mode.html` → 进任意关卡战斗界面
> - **操作**：点开「算法精灵」帮助面板,让 Hint / Guide / Explain 三个按钮都显示
> - **画面要对齐**：左上 HUD 金币数字（如 `💰 20`）+ 三个帮助按钮的消耗标注（`Hint -1` / `Guide -3` / `Explain -5`）同框
> - **证明什么**：分级帮助的成本设计 + 金币 HUD 实时显示

> 没有截图，前端自由发挥
>
> **📸 截图指引 `10-coin-reward-deduct.png`**
>
> - **在哪拍**：同上战斗界面
> - **操作**：先点 Hint（金币 20→19）,再 AC 一道题（金币 19+5=24）
> - **画面要对齐**：`💸 -1` 扣费 toast + `🎉 VICTORY! +5💰` 奖励 toast
> - **证明什么**：金币双向流动 + 事务一致性（LLM 成功才扣费）
> - **备注**：两步 toast 不好同框就分 `10a-coin-deduct.png` + `10b-coin-reward.png` 拼接

---

### 模块六：进度追踪

**用户能做什么**：查看王国通关进度（已通关 X/Y）、关卡解锁状态、历史提交记录（AC / WA / TLE 状态）。

**技术亮点**：关卡顺序解锁机制 + 进度持久化（SQLite Submission 表）,提交状态机覆盖 accepted / wrong_answer / timeout / runtime_error / compile_error。

> ![image-20260705160014865](C:\Users\21349\AppData\Roaming\Typora\typora-user-images\image-20260705160014865.png)
>
> **📸 截图指引 `11-kingdom-progress.png`**
>
> - **在哪拍**：`quest-mode.html` → 主线征程 → 选一个有进度数据的王国
> - **操作**：先随便 AC 2-3 道题制造进度,再回到王国关卡列表
> - **画面要对齐**：王国顶部冒险进度条（「已通关 3/25」）+ 下方关卡列表的 defeated（灰掉/打勾）与 locked（锁住）两种状态同框
> - **证明什么**：关卡顺序解锁机制 + 进度持久化

> 没有截图，前端自由发挥
>
> **📸 截图指引 `12-submission-history.png`**
>
> - **在哪拍**：浏览器 DevTools Network 面板,访问 `/api/progress/submissions`；或前端若有提交记录页就直接截
> - **画面要对齐**：返回 JSON 里能看到 `problem_id / status / submitted_at / coins_earned` 字段,最好有 accepted + wrong_answer 两种状态
> - **证明什么**：提交记录持久化 + 状态机
> - **⚠️ 敏感**：`user_id` 等字段打码

---

## 截图拍摄指引汇总

| 序号 | 文件名                            | 模块            | 去哪截                            | 优先级 |
| ---- | --------------------------------- | --------------- | --------------------------------- | ------ |
| 01   | `01-semantic-search-input.png`    | AI 语义搜索     | `ai-search-demo.html` 搜索框      | ⭐⭐⭐    |
| 02   | `02-semantic-search-result.png`   | AI 语义搜索     | 同上,搜索结果列表                 | ⭐⭐⭐    |
| 03   | `03-agent-hint.png`               | 三级 Agent 帮助 | `quest-mode.html` 战斗界面 → Hint | ⭐⭐⭐    |
| 04   | `04-agent-guide.png`              | 三级 Agent 帮助 | 同上 → Guide                      | ⭐⭐⭐    |
| 05   | `05-agent-explain.png`            | 三级 Agent 帮助 | 同上 → Explain                    | ⭐⭐⭐    |
| 06   | `06-multi-language-solutions.png` | 数据工程        | `quest-mode.html` 代码编辑器      | ⭐⭐     |
| 07   | `07-data-import-log.png`          | 数据工程        | 终端运行导入脚本                  | ⭐⭐     |
| 08   | `08-kingdom-map.png`              | 游戏化世界观    | `quest-mode.html` 主线征程入口    | ⭐⭐⭐    |
| 09   | `09-coin-hud-cost.png`            | 金币经济        | `quest-mode.html` 战斗界面 HUD    | ⭐⭐     |
| 10   | `10-coin-reward-deduct.png`       | 金币经济        | 同上,扣费 + 奖励 toast            | ⭐⭐     |
| 11   | `11-kingdom-progress.png`         | 进度追踪        | `quest-mode.html` 王国关卡列表    | ⭐⭐     |
| 12   | `12-submission-history.png`       | 进度追踪        | DevTools Network / 提交记录页     | ⭐⭐     |

### 推荐拍摄顺序（按依赖关系,避免反复切界面）

1. **`08-kingdom-map.png`** — 进主线征程先截封面
2. **`11-kingdom-progress.png`** — 选个王国,AC 2-3 题制造进度后截
3. **`10b-coin-reward.png`** — 刚才 AC 的题会弹 +💰 toast,顺手截
4. **`09-coin-hud-cost.png`** — 进新关卡,HUD + 帮助按钮同框
5. **`03/04/05-agent-*.png`** — 同一界面连点 Hint/Guide/Explain 截三张
6. **`10a-coin-deduct.png`** — 点 Hint 触发扣费 toast
7. **`06-multi-language-solutions.png`** — 代码编辑器切语言
8. **`01/02-semantic-search-*.png`** — 切到 `ai-search-demo.html` 搜题
9. **`07-data-import-log.png`** — 最后跑终端命令截日志
10. **`12-submission-history.png`** — 这时候提交记录够多了,截 Network

### 敏感信息打码清单

| 截图                        | 需打码内容                              |
| --------------------------- | --------------------------------------- |
| `07-data-import-log.png`    | 本地文件路径（如 `C:/Users/21349/...`） |
| `12-submission-history.png` | `user_id` / `user_email` 字段           |
| 所有含终端/DevTools 的截图  | DeepSeek API key（若出现）              |

---

## 建议省略的截图（附理由）

> **建议省略：真实代码评测控制台**
> 沙箱执行系统已于 2026-07-01 禁用,全部改为 AI 大模型判题（`overview.md` 有记录）。若截图展示「测试用例逐条 pass/fail」会与当前实现不符,且与简历「AI Agent」主线冲突。

> **建议省略：登录注册页**
> 支撑性功能,无 AI 技术说服力,占篇幅不增值。

> **建议省略：多套前端风格切换**
> 早期探索产物（暗色IDE/亮色学术/赛博朋克）,会削弱「AI Agent 平台」的主线叙事。若想展示设计能力,放一张 `08-kingdom-map.png` 足矣。

---

## 项目结构速览

```
algo-quest/
├── quest-mode.html          # 主程序（王国地图 + 战斗刷题 + 精灵面板）
├── ai-search-demo.html      # AI 语义搜索演示页
├── index.html               # 风格对比导航页
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI 路由（search/assistant/progress/problems/auth）
│   │   ├── services/        # 核心服务（agent/search/llm/embedding/importer/judge）
│   │   ├── models/          # SQLAlchemy 模型（User/Problem/Submission/AssistantMessage）
│   │   └── schemas/         # Pydantic 响应模型
│   └── static/              # api-client.js + integration.js（前后端桥梁）
├── solution/                # doocs/leetcode 数据集（3971 题）
└── docs/                    # 文档
```

---

## 简历原文依据

> 本文档的截图清单严格对应简历项目经历「AI Agent 驱动的智能刷题平台」三大亮点：
>
> 1. **AI 语义搜索** → 模块一（截图 01-02）
> 2. **三级 Agent 帮助系统** → 模块二（截图 03-05）
> 3. **数据工程** → 模块三（截图 06-07）
>
> 模块四/五/六为视觉记忆点与系统完整性补充,不与简历冲突。
