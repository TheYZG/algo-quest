# 算法大陆 - 团队开发规范

> Senior Developer 制定 | 2026-06-28 | v1.0

---

## 一、代码原则 (Code Principles)

### 1.1 三大铁律

| # | 原则 | 说明 |
|---|------|------|
| **1** | **先安全，后功能** | 认证不完整上线？绝不。用户金币扣了但LLM失败了？绝不。 |
| **2** | **异常必须显式处理** | 不许 `except Exception: pass`。每个 `except` 都应有理由和日志。 |
| **3** | **先写文档，后写代码** | 每个 PR 必含：API文档更新、使用示例、变更说明。 |

### 1.2 "不该做的事"

```python
# ❌ 错误：把错误当正常返回值
async def call_llm():
    try:
        return await api_call()
    except:
        return "error message"  # 调用者无法区分成功/失败

# ✅ 正确：用异常传达错误
async def call_llm():
    try:
        return await api_call()
    except Exception as e:
        raise LLMServiceError("LLM call failed") from e
```

```python
# ❌ 错误：先扣钱再做事
user.coins -= cost
await db.commit()
result = await llm_call()  # 如果失败了，钱已经扣了

# ✅ 正确：先做事再扣钱
result = await llm_call()  # 成功才往下走
user.coins -= cost
await db.commit()
```

---

## 二、项目架构规范

### 2.1 分层规则

```
api/          → 薄层：参数验证、认证检查、调用 service、返回响应
services/     → 厚层：业务逻辑、外部服务调用
models/       → 纯数据结构：ORM模型、没有业务逻辑
schemas/      → 纯数据结构：Pydantic请求/响应模型
```

**核心原则：API层不放业务逻辑，Service层不访问HTTP请求。**

### 2.2 目录职责

| 目录 | 职责 | 不允许 |
|------|------|--------|
| `api/` | HTTP路由、参数解析、依赖注入 | 业务逻辑、数据库操作 |
| `services/` | 业务逻辑、外部API调用 | HTTP请求/响应操作 |
| `models/` | ORM模型定义 | 任何逻辑 |
| `schemas/` | Pydantic验证模型 | 任何逻辑 |

---

## 三、安全规范

### 3.1 认证与授权

```python
# 所有需要登录的端点必须声明
from app.services.auth import get_current_user

@router.get("/sensitive-data")
async def sensitive(user: User = Depends(get_current_user)):
    ...
```

### 3.2 输入验证

```python
# 用户输入必须经过 Pydantic 验证
class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=8, max_length=100)  # NIST标准

# API 参数必须设限制
page_size: int = Query(default=20, ge=1, le=100)
```

### 3.3 CORS 配置

```python
# ❌ 禁止
allow_origins=["*"] + allow_credentials=True  # W3C明确禁止

# ✅ 正确
allow_origins=["http://localhost:5173", "https://your-domain.com"]
allow_credentials=True
```

### 3.4 敏感信息

- `.env` 文件**绝对不能**提交到 Git
- API Key、密码 hash 绝对不能出现在日志中
- JWT Secret 必须在生产环境设置为64+字符随机值

---

## 四、错误处理规范

### 4.1 异常层次

```
Exception
  └── LLMServiceError          # LLM 调用失败
        └── LLMNotConfiguredError  # LLM 未配置
  └── HTTPException              # FastAPI 内置
```

### 4.2 错误处理模式

```python
try:
    result = await risky_operation()
except LLMNotConfiguredError:
    raise HTTPException(503, "服务未配置")  # 运维问题
except LLMServiceError as e:
    raise HTTPException(502, str(e))        # 上游问题
except Exception:
    logger.exception("Unexpected error")
    raise HTTPException(500, "内部错误")    # 我们自己的问题
```

### 4.3 禁止的反模式

```python
# ❌ 禁止：裸 except
try:
    something()
except:
    pass

# ❌ 禁止：打印后忽略
except Exception as e:
    print(e)

# ✅ 正确：记录日志+转换异常
except Exception as e:
    logger.exception("Failed to process")
    raise ServiceError("Operation failed") from e
```

---

## 五、数据库规范

### 5.1 事务一致性

```python
# ✅ 相关操作放在同一个提交中
async with db.begin():  # 显式事务
    user.coins -= cost
    db.add(TransactionLog(...))
# 要么全部成功，要么全部回滚
```

### 5.2 查询性能

```python
# ❌ 禁止：全量加载到内存再计数
all_users = await db.execute(select(User))
total = len(all_users.scalars().all())  # 100万用户时内存爆炸

# ✅ 正确：用聚合查询
total = (await db.execute(select(func.count()).select_from(User))).scalar()
```

### 5.3 迁移策略

- 开发阶段：`Base.metadata.create_all()` 可以
- 生产环境：必须使用 **Alembic** 管理迁移

---

## 六、API 设计规范

### 6.1 RESTful 命名

| 正确 | 错误 | 说明 |
|------|------|------|
| `GET /api/problems` | `GET /api/getProblems` | 资源名用名词复数 |
| `GET /api/problems/{id}` | `GET /api/problems?id=xxx` | 标识符用路径参数 |
| `POST /api/problems/search` | `GET /api/search_problems` | 复杂查询用POST |

### 6.2 状态码

| 场景 | 状态码 |
|------|--------|
| 创建成功 | 200 (或 201) |
| 参数错误 | 400 |
| 未登录 | 401 |
| 金币不足 | 402 |
| 无权限 | 403 |
| 资源不存在 | 404 |
| 冲突(用户名已存在) | 409 |
| LLM调用失败 | 502 |
| 服务未配置 | 503 |

### 6.3 响应格式

```json
{
  "error": false,
  "data": { ... },
  "detail": "Human readable message"
}
```

---

## 七、代码风格规范

### 7.1 Python 约定

- 类型注解：**必须**使用（Python 3.10+ 风格 `str | None`）
- 字符串：**双引号**用于文档字符串，**单引号**用于普通字符串
- 导入顺序：标准库 → 第三方 → 本地（每组之间空行）
- 每行最大：100字符

### 7.2 命名约定

| 类型 | 风格 | 示例 |
|------|------|------|
| 模块/文件 | snake_case | `problem_service.py` |
| 类 | PascalCase | `ProblemService` |
| 函数/方法 | snake_case | `get_problem_detail()` |
| 常量 | UPPER_SNAKE | `MAX_PAGE_SIZE = 100` |
| 私有属性 | _prefix | `_client`, `_cache` |

### 7.3 Docstring

```python
async def get_hint(problem_id: str, level: str) -> AssistantResponse:
    """
    获取分级帮助。

    Args:
        problem_id: 题目ID（4位数字）
        level: 帮助等级 hint/guide/explain

    Returns:
        助手的回复，包含消耗金币数

    Raises:
        HTTPException(402): 金币不足
        HTTPException(404): 题目不存在
        HTTPException(502): LLM调用失败
    """
```

---

## 八、Git 工作流

### 8.1 分支命名

```
feature/xxx      → 新功能
fix/xxx          → Bug修复
refactor/xxx     → 重构（不改变行为）
docs/xxx         → 文档更新
```

### 8.2 Commit 规范

```
feat: 添加 AI 语义搜索功能
fix: 修复 LLM 失败时金币仍然扣除的bug
refactor: 重构题目列表查询，添加内存缓存
docs: 更新 API 文档
```

### 8.3 Code Review 必查项

- [ ] 认证是否正确应用
- [ ] 输入验证是否充分
- [ ] 是否存在金币/积分扣减不一致的风险
- [ ] 异常是否正确传播（没有 `except: pass`）
- [ ] 数据库操作是否使用正确的查询方式
- [ ] API 响应模型是否正确定义
- [ ] 日志是否记录关键操作

---

## 九、测试规范（后续推行）

### 9.1 最低覆盖

| 模块 | 测试类型 | 目标覆盖 |
|------|----------|----------|
| `services/auth.py` | 单元测试 | 90%+ |
| `services/search.py` | 集成测试 (mock ChromaDB) | 80%+ |
| `api/auth.py` | API测试 | 90%+ |
| `api/assistant.py` | API测试 (mock LLM) | 80%+ |

### 9.2 测试结构

```python
# 测试文件命名: test_{module_name}.py
# 放在 tests/ 目录下

def test_login_success():
    """正常登录应返回token"""

def test_login_wrong_password():
    """错误密码应返回401"""

def test_submit_earns_coins():
    """首次AC应获得金币奖励"""

def test_llm_failure_rolls_back():
    """LLM失败时金币不应扣除"""
```

---

## 十、部署检查清单

- [ ] `SECRET_KEY` 已设置为64+位随机字符串
- [ ] `CORS_ORIGINS` 已配置正确的生产域名
- [ ] `DEBUG=False`
- [ ] 数据库已使用 Alembic 迁移
- [ ] 日志级别设置为 WARNING（生产）
- [ ] API 速率限制已启用
- [ ] 所有 `.env` 变量已填写
- [ ] 健康检查端点正常工作
