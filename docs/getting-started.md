# 算法大陆 — 从零开始运行指南

> 面向：开发者 | 系统：Windows/Mac/Linux | 预计时间：15分钟

---

## 目录

1. [环境准备](#1-环境准备)
2. [获取项目](#2-获取项目)
3. [配置 LLM](#3-配置-llm)
4. [安装依赖](#4-安装依赖)
5. [启动后端](#5-启动后端)
6. [导入数据](#6-导入数据)
7. [验证测试](#7-验证测试)
8. [前端集成](#8-前端集成)
9. [常见问题](#9-常见问题)

---

## 1. 环境准备

### 必须安装

| 工具 | 最低版本 | 检查命令 |
|------|----------|----------|
| Python | 3.10+ | `python --version` |
| pip | 22+ | `pip --version` |

### 验证

```bash
python --version   # 应该输出 Python 3.10.x 或更高
pip --version      # 应该输出 pip 22.x 或更高
```

---

## 2. 获取项目

```bash
cd /your/workspace
# 确保项目目录结构如下：
# .
# ├── backend/           # 后端代码
# ├── solution/          # LeetCode 题目数据（3971道题）
# ├── quest-mode.html    # 前端主页面
# └── ai-search-demo.html # AI搜索演示页
```

---

## 3. 配置 LLM

### 3.1 创建 .env 配置文件

```bash
cd backend
cp .env.example .env
```

### 3.2 编辑 .env

打开 `backend/.env`，填入你的配置：

```env
# 安全密钥（生成方式见下方）
SECRET_KEY=your-64-char-random-string

# DeepSeek 配置（推荐，性价比高）
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=sk-your-deepseek-key-here
LLM_MODEL=deepseek-v4-flash

# 或者用 OpenAI
# LLM_BASE_URL=https://api.openai.com/v1
# LLM_API_KEY=sk-your-openai-key
# LLM_MODEL=gpt-4o-mini

# 或者本地 Ollama
# LLM_BASE_URL=http://localhost:11434/v1
# LLM_API_KEY=ollama
# LLM_MODEL=qwen2.5:7b
```

### 3.3 支持的任何 OpenAI 兼容 API

| 服务商 | LLM_BASE_URL |
|--------|-------------|
| DeepSeek | `https://api.deepseek.com` |
| OpenAI | `https://api.openai.com/v1` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Moonshot | `https://api.moonshot.cn/v1` |
| Ollama(本地) | `http://localhost:11434/v1` |
| vLLM(本地) | `http://localhost:8000/v1` |

---

## 4. 安装依赖

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Mac/Linux:
# source venv/bin/activate

# 安装依赖（首次安装约5-10分钟）
pip install -r requirements.txt
```

> 💡 建议用清华镜像加速：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

### 依赖说明

| 包名 | 用途 | 大小 |
|------|------|------|
| `fastapi` + `uvicorn` | Web框架 | ~5MB |
| `chromadb` | 向量数据库 | ~50MB |
| `sentence-transformers` + `text2vec-base-chinese` | 中文向量模型 | ~400MB |
| `sqlalchemy` + `aiosqlite` | 关系数据库 | ~5MB |
| `openai` | LLM调用 | ~2MB |

---

## 5. 启动后端

```bash
cd backend

# Windows (Git Bash):
bash start.sh

# 或直接：
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

看到以下输出表示启动成功：

```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 验证启动

浏览器打开 `http://localhost:8000/api/health`，应返回：

```json
{"status":"ok","app":"算法大陆 - AI Agent 刷题平台","version":"1.0.0"}
```

---

## 6. 导入数据

### 6.1 导入题目到向量数据库

**方法一：通过 API（推荐）**

```bash
# Windows PowerShell / Mac Terminal:
curl -X POST http://localhost:8000/api/admin/import
```

返回：

```json
{"success": true, "message": "导入已在后台启动，请稍后查询状态"}
```

**方法二：通过浏览器**

打开 `http://localhost:8000/api/docs` → 找到 `POST /api/admin/import` → 点击 "Try it out" → "Execute"

### 6.2 查看导入进度

```bash
curl http://localhost:8000/api/admin/import-status
```

```json
{
  "running": true,
  "stats": null
}
```

导入完成后：

```json
{
  "running": false,
  "stats": {
    "total": 3971,
    "imported": 3971,
    "skipped": 0,
    "errors": 0,
    "by_difficulty": {"Easy": 951, "Medium": 2074, "Hard": 946}
  }
}
```

> ⏱️ 导入 3971 道题约需 15-30 分钟（取决于电脑性能），首次导入还需下载 text2vec 模型（~400MB）。

### 6.3 验证数据

```bash
curl http://localhost:8000/api/admin/chroma-stats
# {"count": 3971, "name": "leetcode_problems"}
```

---

## 7. 验证测试

### 7.1 测试注册登录

```bash
# 注册
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"dev","password":"password123"}'

# 返回：access_token + 用户信息（初始20金币）
```

### 7.2 测试 AI 语义搜索

```bash
curl -X POST http://localhost:8000/api/problems/search \
  -H "Content-Type: application/json" \
  -d '{"query":"类似背包问题的动态规划题目","top_k":5}'
```

使用 text2vec-base-chinese 模型后，中文搜索结果会更加精准。

### 7.3 测试 AI 助手对话

```bash
# 先获取 token（从上一步注册返回的 access_token）
TOKEN="your-token-here"

# 自由对话
curl -X POST http://localhost:8000/api/assistant/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"背包问题为什么用动态规划而不是贪心？"}'
```

### 7.4 测试分级帮助

```bash
# 获取提示（消耗1金币）
curl -X POST http://localhost:8000/api/assistant/hint \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"problem_id":"0001","level":"hint"}'

# 获取引导（消耗3金币）
# level: hint / guide / explain
```

### 7.5 查看 API 文档

浏览器打开 `http://localhost:8000/api/docs` — 所有接口可在线测试。

---

## 8. 前端集成

### 8.1 使用 JS SDK

```html
<script src="http://localhost:8000/static/api-client.js"></script>
<script>
// 1. 登录
const { access_token, user } = await ApiClient.auth.login('dev', 'password123');
ApiClient.setToken(access_token);

// 2. AI 搜索
const results = await ApiClient.problems.search('动态规划入门题');

// 3. AI 助手
const help = await ApiClient.assistant.getHint('0001', 'hint');

// 4. 提交代码
const result = await ApiClient.progress.submit('0001', 'Two Sum', 'python', code);
</script>
```

### 8.2 打开演示页面

双击 `ai-search-demo.html`（需后端运行中）。

### 8.3 对接主页面

`quest-mode.html` 可通过 `ApiClient` 全局对象调用后端所有功能。

---

## 9. 常见问题

### Q: 导入时 "No module named 'xxx'"

```bash
pip install -r requirements.txt  # 确保所有依赖安装完毕
```

### Q: "No such file or directory: ../solution"

.senv 中的 `LEETCODE_DATA_DIR` 路径不对。确保相对于 `backend/` 目录能找到 `solution/` 文件夹。

### Q: AI 助手返回 "未配置"

检查 `.env` 中的 `LLM_API_KEY` 是否填写正确。

### Q: 端口 8000 被占用

```bash
# Windows
netstat -ano | findstr :8000
taskkill /F /PID <PID>

# Mac/Linux
lsof -i :8000
kill -9 <PID>
```

### Q: 搜索效果不好

`text2vec-base-chinese` 对中文语义搜索效果优于通用模型。如果还想更好，可以考虑：

- `BAAI/bge-large-zh-v1.5`（1024维，约1.3GB）
- `moka-ai/m3e-base`（768维，约400MB）

修改 `config.py` 中的 `EMBEDDING_MODEL` 后重新导入即可。

### Q: 如何重置所有数据

```bash
# 清空向量数据库
rm -rf backend/chroma_data/

# 清空用户数据
rm -rf backend/data/

# 重启 + 重新导入
```

---

## 项目结构速查

```
backend/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置（在这里改 embedding 模型、LLM 等）
│   ├── database.py          # SQLite 数据库
│   ├── vectordb.py          # ChromaDB 向量库
│   ├── api/                 # API 路由
│   │   ├── auth.py          # 登录/注册
│   │   ├── problems.py      # 题目 + 搜索
│   │   ├── assistant.py     # AI 助手
│   │   ├── progress.py      # 做题进度
│   │   └── admin.py         # 数据管理
│   ├── models/              # 数据库模型
│   ├── schemas/             # 请求/响应模型
│   └── services/            # 业务逻辑
│       ├── agent.py         # AI 助手核心
│       ├── embedding.py     # 向量化
│       ├── importer.py      # 数据导入
│       ├── llm.py           # LLM 调用
│       ├── search.py        # 语义搜索
│       └── problems.py      # 题目服务
├── static/api-client.js     # 前端 JS SDK
├── .env                     # 环境配置（你的密钥在这里）
├── requirements.txt
└── start.sh
```

---

## 快速命令速查

```bash
# 启动
cd backend && uvicorn app.main:app --reload --port 8000

# 导入数据
curl -X POST http://localhost:8000/api/admin/import

# 查看数据量
curl http://localhost:8000/api/admin/chroma-stats

# 注册用户
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"me","password":"mypassword123"}'

# 语义搜索
curl -X POST http://localhost:8000/api/problems/search \
  -H "Content-Type: application/json" \
  -d '{"query":"链表反转","top_k":5}'

# API 文档
open http://localhost:8000/api/docs
```
