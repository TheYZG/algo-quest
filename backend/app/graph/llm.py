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
