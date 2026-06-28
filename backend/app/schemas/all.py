"""
Pydantic 请求/响应模型
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


# ============================================================
# 用户
# ============================================================
class UserRegister(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=8, max_length=100, description="至少8位密码")
    email: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserProfile"


class UserProfile(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    coins: int
    total_solved: int
    easy_solved: int
    medium_solved: int
    hard_solved: int
    adventure_level: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# 题目
# ============================================================
class ProblemBrief(BaseModel):
    """题目列表项"""
    id: str
    number: int
    title: str
    title_cn: str
    slug: str = ""
    difficulty: str  # Easy / Medium / Hard
    tags: list[str] = []
    ac_rate: float = 0.0
    kingdom: str = ""
    kingdom_emoji: str = ""
    kingdoms: list[str] = []  # 该题所属的所有王国


class ProblemDetail(BaseModel):
    """题目详情"""
    id: str
    number: int
    title: str
    title_cn: str
    slug: str = ""
    difficulty: str
    tags: list[str] = []
    description_html: str
    description_cn_html: str
    likes: int = 0
    dislikes: int = 0
    accepted: int = 0
    submissions: int = 0
    hints: list[str] = []
    solutions: dict[str, str] = {}  # language -> code
    kingdom: str = ""
    kingdom_emoji: str = ""
    kingdoms: list[str] = []  # 该题所属的所有王国


class ProblemListResponse(BaseModel):
    """题目列表响应"""
    total: int
    page: int
    page_size: int
    problems: list[ProblemBrief]


# ============================================================
# 搜索
# ============================================================
class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500, description="自然语言搜索描述")
    top_k: int = Field(default=10, ge=1, le=50)
    difficulty: Optional[str] = None  # Easy / Medium / Hard
    tags: Optional[list[str]] = None


class SearchResult(BaseModel):
    """搜索结果项"""
    problem: ProblemBrief
    relevance: float  # 相似度分数


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


# ============================================================
# AI 助手
# ============================================================
class AssistantRequest(BaseModel):
    """通用助手对话请求"""
    message: str = Field(min_length=1, max_length=2000)
    problem_id: Optional[str] = None
    problem_context: Optional[dict] = None  # 当前题目上下文
    history: Optional[list[dict]] = None  # 对话历史


class HintRequest(BaseModel):
    """获取提示请求"""
    problem_id: str
    level: str = Field(default="hint", description="hint / guide / explain")
    conversation_history: Optional[list[dict]] = None


class AssistantResponse(BaseModel):
    """助手回复"""
    message: str
    help_level: Optional[str] = None  # hint / guide / explain / chat
    coins_spent: int = 0
    coins_remaining: int = 0
    related_problems: Optional[list[ProblemBrief]] = None


# ============================================================
# 提交
# ============================================================
class SubmissionRequest(BaseModel):
    problem_id: str
    problem_title: str
    language: str
    code: str


class SubmissionResponse(BaseModel):
    id: str
    problem_id: str
    status: str
    language: str
    result: Optional[str] = None
    coins_earned: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class SubmissionListResponse(BaseModel):
    total: int
    submissions: list[SubmissionResponse]


# ============================================================
# 标签/王国
# ============================================================
class TagStats(BaseModel):
    tag: str
    count: int
    kingdom: str


class KingdomInfo(BaseModel):
    id: str  # 前端卡片 ID
    name: str  # 中文王国名
    emoji: str
    color: str  # 主题色
    bg: str  # 卡片背景色
    glow: str  # 光效颜色
    chaos: bool = False  # 是否混沌领域
    tags: list[str] = []
    total_problems: int
    easy_count: int
    medium_count: int
    hard_count: int
