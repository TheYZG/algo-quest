# vNext 版本总结 — 多 Agent 议会编排

> 发布日期：2026-08-20 ｜ 对应计划：`docs/superpowers/plans/2026-08-20-multi-agent-parliament.md` ｜ 设计：`docs/superpowers/specs/2026-08-20-multi-agent-design.md`

## 相比上一版本的新增内容

1. **LangGraph 议会编排**：Supervisor（精灵女王）+ 导师/判题官/侦察兵/军师 四专家循环派单，
   新增 `backend/app/graph/` 包（state/tools/agents/graph）
2. **判题交叉验证**：判题子图条件触发复核官（置信度 < 0.7 或判错），分歧时确定性仲裁
3. **SSE 流式协作时间线**：`POST /api/assistant/chat/stream` + 前端议会面板实时渲染
4. **跨会话记忆**：AsyncSqliteSaver checkpointer（thread_id = user:problem）
5. **Agent 名册 API**：`GET /api/assistant/agents`
6. **测试体系**：pytest + pytest-asyncio，覆盖 State/路由/专家/判题/图组装/API 层

## 实现过程中的关键决策

落地时与原计划的 4 个主要偏差及理由：

1. **langgraph-checkpoint-sqlite 0.2.1 → 2.0.1**：0.2.x 的 `AsyncSqliteSaver` 与
   langgraph 1.x 图运行时不兼容（checkpoint 协议版本不匹配），升级到 2.0.1 后协议对齐，
   API 面无变化（`AsyncSqliteSaver(aiosqlite.connect(path))` 用法保持不变）。
2. **create_react_agent 的 `prompt=` → `state_modifier=`**：随 langgraph 升级，
   `create_react_agent` 移除了 `prompt` 参数，改用 `state_modifier` 注入人格系统提示词，
   六个 Agent（queen 除外）统一迁移。
3. **`get_parliament_graph` 改 async 工厂**：`AsyncSqliteSaver` 构造时调用
   `asyncio.get_running_loop()` 并把 saver 绑定到当前事件循环，进程内无运行循环时构造
   直接抛 RuntimeError，因此图的单例构建必须放到 async 工厂里（FastAPI 请求处理器内
   首次调用时完成），不能在模块导入期同步构建。
4. **judge_graph 的 reviewer → arbitrate 改无条件边**：原计划只在"分歧"时进仲裁；
   实现时改为复核完成后一律经过 arbitrate 节点（`resolve_verdict` 内部区分
   一致/分歧：一致时采纳判题官并取双方最高置信度、标记 reviewed；分歧时倾向复核官、
   标记 arbitrated），保证复核后的裁决出口唯一、置信度合并逻辑集中在一处。

## 端到端验收结果（2026-08-20，真实服务器 + DeepSeek deepseek-v4-flash）

环境：`uvicorn app.main:app --port 8000`，测试账号 e2e_tester（初始 20 金币），
回归测试 **34 passed**（其中 1 个为验收期修复后转绿，见下）。

| # | 场景 | 结果 | 实际记录 |
|---|------|------|----------|
| 9 | Agent 名册 | ✅ 通过 | GET /api/assistant/agents → 200，返回 6 个：queen/tutor/judge/scout/planner/reviewer |
| 1 | 闲聊直通 | ✅ 通过（带观察项） | POST /chat {"message":"你好"} → 200，coins_spent=0，help_level=chat，8.2s；但 message 为兜底文案「议会暂时没有可用的答复…」——queen 对问候判定 finish 未派任何专家，summarize 无产出走 fallback（graph.py:69）。建议后续让 queen 对问候直接拟人回应 |
| 2 | 卡题求助多专家 | ✅ 通过 | 200，39.8s，coins_spent=1；timeline 实际路径：queen(识别 teaching)→scout(查提交记录)→queen→tutor(讲解题)→queen(汇总收工)→final；agents_involved=[scout, tutor]，回复完整教学文案 |
| 3a | hint 级帮助 | ✅ 通过（验收期修复 1 个 bug） | 首次 500：`_base_graph_input` 直接取 `request.message` 而 HintRequest 无该字段（AttributeError）；修复为 getattr 兼容合成请求语义（assistant.py:61）后重试 → 200，33s，help_level=hint，coins_spent=1，回复 251 字提示级（两个思考方向、不泄底）。观察：pinned 路径 queen→tutor 循环 6 轮后由防死循环上限收工，轮次偏多但正确收敛 |
| 3b | SSE 流式 | ✅ 通过 | 200，26.2s；14 条 data 事件：多条 timeline（agent_start/agent_done）+ 末尾两条 type=final（timeline 的 final 事件 + 最终结构化结果）；final.message 为导师的数据结构选型讲解，coins_spent=1 |
| 4 | 判题高置信度 | ✅ 结构通过（LLM 裁决被模型兼容性阻断） | POST /progress/submit 哈希表正确解 → 200，9.4s，status=accepted，coins_earned=5（Easy 首次 AC）；ai_feedback.execution_mode=="ai"，含 analysis/confidence/issues/suggestions/comparison ✓。但 judge 的 response_format 结构化输出触发 DeepSeek thinking 模式不支持 tool_choice 的 400，走了「AI 判题服务不可用默认通过」降级路径（恰好实证降级保护有效）。真实裁决需换非 thinking 模型验证 |
| 7 | 跨请求记忆 | ✅ 接口通过 / ⚠️ 上下文未体现 | 同 problem_id 连续两次 /chat 均 200（49.1s / 29.1s），扣费正常；checkpointer 确认写入（thread `user:0001` 累计 115 个 checkpoint）；但第二次回复称「找不到此前学习记录」——specialist 节点 prompt 只注入 `state['messages'][-1]` 最新一条（specialists.py:125），历史消息已持久化但未进入专家上下文，属「已存未用」 |
| 5 | 触发复核 | 留人工观察 | 依赖 LLM 恰好低置信度/判错，概率行为；触发条件与复核流程逻辑已由单元测试覆盖（test_judge_flow.py 8 个用例 + test_graph.py 判题子图 2 用例） |
| 6 | 仲裁 | 留人工观察 | 同上；resolve_verdict 确定性仲裁逻辑已由 test_judge_flow.py「分歧时倾向复核官」等用例覆盖 |
| 8 | LLM 失败不扣费 | 留人工验证 | 不破坏 .env 配置；降级路径已在场景 4 中被间接实证（判题 LLM 400 → 服务可用性降级而非 500/错误扣费） |

**验收期顺手修复的生产 bug（已含在本版）：**

- `app/api/progress.py:273`：首次 AC 判断原用 `scalar_one_or_none()`，同题多次 AC 时
  查询返回多行直接抛 `MultipleResultsFound`（任何真实用户第二次 AC 同一题必 500，
  被测试库残留数据暴露）；改为 `scalars().first()`。
- `app/api/assistant.py:61`：`_base_graph_input` 取 `request.message` 对
  HintRequest 抛 AttributeError（/api/assistant/hint 端点 100% 500）；改为
  getattr 兼容并按 level 合成请求语义。

修复后全量回归 34 passed。

## 需人工验证清单

- [ ] 浏览器视觉验收：6 套主题下议会面板（时间线滚动、Agent 头像、final 消息渲染）
- [ ] DeepSeek / OpenAI 双后端切换（改 LLM_BASE_URL/LLM_MODEL 后图链路全通）
- [ ] 旧前端 `ai-search-demo.html` 兼容性（新旧接口并存）
- [ ] 金币结算失败不扣费（LLM 异常时余额不变，需断网/断 key 验证）
- [ ] 判题复核的概率性触发观察（连续提交边界用例代码，观察 reviewer/arbitrate 时间线）
- [ ] 判题真实裁决：切换非 thinking 模型（如 deepseek-chat 或关闭思考）后确认
      judge LLM 结构化裁决可正常返回（当前 deepseek-v4-flash thinking 模式与
      response_format 的 tool_choice 冲突，见场景 4）

## 已知限制

- **SSE 暂不含 token 级流式**：summarize 多专家汇总路径已预留 `final_reply` 标签
  （graph.py:67 `model.with_config(tags=["final_reply"])`），SSE 端点按此标签做
  token 级转发的管线后续可开。
- **判题子图无 checkpointer**：judge_graph 为无状态直调（/progress/submit 一次性
  执行），复核/仲裁中间态不落盘。
- **跨请求记忆「已存未用」**：AsyncSqliteSaver 正常持久化 messages（115
  checkpoints/单 thread 实测），但专家节点 prompt 仅注入最新一条 human message，
  历史未进入 LLM 上下文；需要把历史消息（或压缩摘要）拼入专家任务简报后记忆才真正生效。
- **问候语兜底文案**：queen 对 FREE_GREETINGS 判 finish 不派专家时，summarize 无
  产出走「议会暂时没有可用的答复」兜底，体验欠佳。
- **pinned 帮助轮次偏多**：/hint 的 pinned 路径实测 queen→tutor 循环 6 轮才收工
  （防死循环上限兜底），可通过在 queen 路由 prompt 中注入「已提供过帮助」信号优化。
