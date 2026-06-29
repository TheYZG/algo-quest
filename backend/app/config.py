"""
应用配置 - 集中管理所有环境变量和配置项
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
import os
import secrets


class Settings(BaseSettings):
    # 服务器
    APP_NAME: str = "算法大陆 - AI Agent 刷题平台"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # CORS - 前端域名列表（生产环境必须配置）
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # Next.js dev server
        "http://localhost:8080",   # 通用 dev server
        "http://127.0.0.1:5500",   # Live Server
        "http://127.0.0.1:8000",   # 同源
        "null",                     # file:// 协议
    ]

    # 安全
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24小时

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """确保 SECRET_KEY 已设置安全的随机值"""
        invalid_defaults = [
            "change-me", "change-me-in", "your-secret-key",
            "changeme", "secret", "default",
        ]
        v = (v or "").strip().lower()
        if not v or any(d in v for d in invalid_defaults):
            # 开发环境自动生成临时密钥（生产环境会在启动时警告）
            return "dev-temp-" + secrets.token_hex(32)
        return v

    # 数据库 - 使用绝对路径避免跨平台歧义
    DATABASE_PATH: str = "./data/leetcode.db"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    CHROMA_COLLECTION: str = "leetcode_problems"

    # Embedding 模型
    EMBEDDING_MODEL: str = "shibing624/text2vec-base-chinese"
    EMBEDDING_DIM: int = 768

    # LLM 配置（兼容 OpenAI API）
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2048
    LLM_TIMEOUT: float = 30.0  # 秒

    # AI 助手
    ASSISTANT_NAME: str = "算法精灵"
    ASSISTANT_EMOJI: str = "🧚"
    HINT_COST: int = 1       # 思路提示消耗金币
    GUIDE_COST: int = 3      # 部分引导消耗金币
    EXPLAIN_COST: int = 5    # 详细解析消耗金币
    INITIAL_COINS: int = 20  # 新用户初始金币

    # 数据导入
    LEETCODE_DATA_DIR: str = "../solution"

    # 密码策略
    PASSWORD_MIN_LENGTH: int = 8

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
