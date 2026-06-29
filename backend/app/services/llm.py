"""
LLM 服务 - OpenAI 兼容 API 调用
使用明确的异常类型，避免将错误当作正常返回值
"""
import logging
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMServiceError(Exception):
    """LLM 服务异常 - 调用失败时抛出，上层可据此决定是否回滚扣费"""
    pass


class LLMNotConfiguredError(LLMServiceError):
    """LLM 未配置"""
    pass


_client = AsyncOpenAI(
    base_url=settings.LLM_BASE_URL,
    api_key=settings.LLM_API_KEY,
)


async def chat_completion(
    messages: list[dict],
    temperature: float | None = None,
    max_tokens: int | None = None,
    stream: bool = False,
) -> str:
    """
    调用 LLM 进行对话

    Args:
        messages: 对话消息列表 [{"role": ..., "content": ...}]
        temperature: 温度参数 (0-2)
        max_tokens: 最大生成 token 数
        stream: 是否流式输出

    Returns:
        LLM 回复文本

    Raises:
        LLMNotConfiguredError: API Key 未配置
        LLMServiceError: API 调用失败（网络错误、超时、限流等）
    """
    if not settings.LLM_API_KEY:
        raise LLMNotConfiguredError(
            "AI 助手未配置。请在 .env 中设置 LLM_API_KEY"
        )

    try:
        response = await _client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            temperature=temperature or settings.LLM_TEMPERATURE,
            max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
            stream=stream,
            timeout=settings.LLM_TIMEOUT,
        )

        if stream:
            content_parts: list[str] = []
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    content_parts.append(chunk.choices[0].delta.content)
            return "".join(content_parts)

        content = response.choices[0].message.content
        return content or ""

    except LLMServiceError:
        raise
    except Exception as e:
        raise LLMServiceError(f"AI 助手暂时不可用：{e}") from e
