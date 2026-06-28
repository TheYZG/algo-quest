# 算法大陆 - 后端开发文档

## 快速开始

### 1. 安装依赖
```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置 LLM
编辑 `.env` 文件，填入你的 API Key:
```
LLM_API_KEY=sk-your-key-here
LLM_BASE_URL=https://api.openai.com/v1  # 或任何兼容API
LLM_MODEL=gpt-4o-mini
```

### 3. 启动服务器
```bash
bash start.sh
# 或手动:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 导入题目数据（首次使用）
```bash
# 方法1: 通过API
curl -X POST http://localhost:8000/api/admin/import

# 方法2: 查看进度
curl http://localhost:8000/api/admin/chroma-stats
```

## API 文档
启动后访问: http://localhost:8000/api/docs

## 核心特性

### 🔍 AI 语义搜索
用自然语言描述你要找的题目，AI 自动理解意图并返回最匹配的结果。

```javascript
// 示例: "类似背包问题的动态规划入门题"
POST /api/problems/search
{
    "query": "类似背包问题的动态规划入门题",
    "top_k": 10,
    "difficulty": "Medium"  // 可选
}
```

### 🧚 AI 助手（算法精灵）
三级帮助系统，消耗金币获取帮助：

| 等级 | 说明 | 消耗 |
|------|------|------|
| hint | 思路提示 | 1 💰 |
| guide | 部分引导（伪代码） | 3 💰 |
| explain | 完整解析+代码 | 5 💰 |

```javascript
// 获取提示
POST /api/assistant/hint
{
    "problem_id": "0001",
    "level": "hint"  // hint / guide / explain
}

// 自由对话
POST /api/assistant/chat
{
    "message": "这道题我想到用暴力的思路对吗？",
    "problem_id": "0001"
}
```

## 技术架构

```
backend/
├── app/
│   ├── main.py          # FastAPI 入口
│   ├── config.py        # 配置管理
│   ├── database.py      # SQLAlchemy + SQLite
│   ├── vectordb.py      # ChromaDB 客户端
│   ├── models/          # ORM 模型
│   │   ├── user.py
│   │   ├── submission.py
│   │   └── assistant.py
│   ├── schemas/         # Pydantic 模型
│   │   └── all.py
│   ├── api/             # API 路由
│   │   ├── auth.py      # 认证
│   │   ├── problems.py  # 题目 + 搜索
│   │   ├── assistant.py # AI 助手
│   │   ├── progress.py  # 进度追踪
│   │   └── admin.py     # 数据管理
│   └── services/        # 业务逻辑
│       ├── agent.py     # AI Agent 核心
│       ├── auth.py      # 认证逻辑
│       ├── embedding.py # 向量生成
│       ├── importer.py  # 数据导入
│       ├── llm.py       # LLM 调用
│       ├── problems.py  # 题目查询
│       └── search.py    # 语义搜索
├── static/
│   └── api-client.js    # 前端 JS SDK
└── chroma_data/         # ChromaDB 持久化
```

## 支持的 LLM 后端

任何兼容 OpenAI API 的服务都可以：

- **OpenAI**: `LLM_BASE_URL=https://api.openai.com/v1`
- **DeepSeek**: `LLM_BASE_URL=https://api.deepseek.com/v1`
- **通义千问**: `LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- **Ollama (本地)**: `LLM_BASE_URL=http://localhost:11434/v1`
- **Moonshot**: `LLM_BASE_URL=https://api.moonshot.cn/v1`

## 前端集成

```html
<script src="/static/api-client.js"></script>
<script>
// 1. 登录
const { user, access_token } = await ApiClient.auth.login('username', 'password');
ApiClient.setToken(access_token);

// 2. AI 搜索
const results = await ApiClient.problems.search('链表反转的经典面试题');

// 3. AI 助手帮助
const help = await ApiClient.assistant.getHint('0001', 'hint');
console.log(help.message); // 算法精灵的提示

// 4. 提交代码
const result = await ApiClient.progress.submit('0001', 'Two Sum', 'python', code);
</script>
```

## 后续可扩展

- [ ] Docker sandbox 真实代码评测
- [ ] WebSocket 实时 AI 对话
- [ ] 用户排行榜
- [ ] 每日一题推送
- [ ] 代码执行可视化
- [ ] 多人对战模式
