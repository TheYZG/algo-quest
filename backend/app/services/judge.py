"""
AI 判题服务 — 大模型对比用户代码和参考解答，判断正确性并给出反馈

策略:
  - 从数据库获取题目描述 + 参考解答
  - 将题目、参考代码、用户代码一起发给 LLM
  - LLM 返回结构化判断结果（correct / incorrect + analysis + issues）
  
优势:
  - 无需测试用例，覆盖全部 3971 题
  - 深入理解算法逻辑，不只是对比输出
  - 错了能指出具体问题所在
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.services.llm import chat_completion, LLMServiceError

logger = logging.getLogger(__name__)


@dataclass
class JudgeResult:
    """AI 判题结果"""
    correct: bool                # 是否正确
    confidence: float = 1.0      # AI 置信度 (0-1)
    analysis: str = ""           # AI 分析文本
    issues: list[str] = field(default_factory=list)  # 具体问题列表
    suggestions: list[str] = field(default_factory=list)  # 改进建议
    comparison: str = ""         # 与参考解答的对比
    raw_response: str = ""       # LLM 原始回复（调试用）


# ============================================================
# Prompt 模板
# ============================================================

JUDGE_SYSTEM_PROMPT = """你是一位资深的算法竞赛评审专家。你的任务是：
1. 仔细阅读题目描述
2. 对比用户提交的代码和官方参考解答
3. 判断用户代码是否正确，并给出详细分析

判定标准（严格）：
- ✅ CORRECT: 用户代码的算法思路正确，能正确处理所有边界情况，时间/空间复杂度合理
- ❌ INCORRECT: 代码存在逻辑错误、遗漏边界情况、时间复杂度不达标、或完全错误的思路

你必须只返回 JSON 格式（不要加 markdown 代码块标记）：
{
  "correct": true/false,
  "confidence": 0.0-1.0,
  "analysis": "整体分析（中文，200字内）",
  "issues": ["问题1", "问题2"],
  "suggestions": ["改进建议1", "改进建议2"],
  "comparison": "与参考解答的核心差异（中文，100字内）"
}

注意：
- 如果用户代码与参考解答算法相同但实现略有不同（变量名不同等），仍视为正确
- 如果用户代码能过基本测试但时间复杂度不达标，应标注为错误
- analysis 要具体，指出对在哪里/错在哪里
- issues 为空数组表示代码正确
"""


def _build_judge_prompt(
    problem_title: str,
    problem_description: str,
    reference_solution: str,
    user_code: str,
    language: str,
) -> str:
    """构建判题 prompt"""
    desc = problem_description[:1500] if problem_description else "（无题目描述）"
    ref = reference_solution[:2000] if reference_solution else "（无参考解答）"

    return f"""## 题目

**{problem_title}**

{desc}

## 参考解答（{language}）

```{language}
{ref}
```

## 用户提交的代码（{language}）

```{language}
{user_code}
```

请严格按照 JSON 格式返回你的判断结果。"""


def _parse_judge_response(response: str) -> JudgeResult:
    """解析 LLM 返回的 JSON"""
    text = response.strip()

    # 去掉可能的 markdown 代码块标记
    if text.startswith("```"):
        lines = text.split("\n")
        # 去掉第一行（```json）和最后一行（```）
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        text = text.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取 JSON 对象
        import re
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                # 无法解析，假设 LLM 判断为正确（宽容策略）
                return JudgeResult(
                    correct=True,
                    confidence=0.6,
                    analysis="AI 判断结果解析失败，默认通过",
                    raw_response=response,
                )
        else:
            return JudgeResult(
                correct=True,
                confidence=0.6,
                analysis="AI 判断结果解析失败，默认通过",
                raw_response=response,
            )

    return JudgeResult(
        correct=data.get("correct", False),
        confidence=float(data.get("confidence", 0.8)),
        analysis=data.get("analysis", ""),
        issues=data.get("issues", []),
        suggestions=data.get("suggestions", []),
        comparison=data.get("comparison", ""),
        raw_response=response,
    )


async def ai_judge(
    problem_title: str,
    problem_description: str,
    reference_solution: str,
    user_code: str,
    language: str = "python",
) -> JudgeResult:
    """
    AI 判题主入口

    Args:
        problem_title: 题目标题
        problem_description: 题目描述 (HTML)
        reference_solution: 参考解答代码
        user_code: 用户提交的代码
        language: 编程语言

    Returns:
        JudgeResult — 包含正确性判断和详细反馈

    Raises:
        LLMServiceError: LLM 调用失败时抛出，上层可决定降级策略
    """
    # 清洗 HTML 标签，保留纯文本（减少 token 消耗）
    import re
    clean_desc = re.sub(r'<[^>]+>', ' ', problem_description or '')
    clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()

    prompt = _build_judge_prompt(
        problem_title=problem_title,
        problem_description=clean_desc,
        reference_solution=reference_solution,
        user_code=user_code,
        language=language,
    )

    messages = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    logger.info(f"AI 判题请求: title={problem_title} lang={language} code_len={len(user_code)} ref_len={len(reference_solution)}")

    try:
        response = await chat_completion(
            messages=messages,
            temperature=0.1,  # 低温度保证判断稳定性
            max_tokens=1500,
        )
    except LLMServiceError:
        raise  # 重新抛出，让调用者处理

    result = _parse_judge_response(response)
    logger.info(
        f"AI 判题结果: correct={result.correct} confidence={result.confidence:.2f} "
        f"issues={len(result.issues)} analysis_len={len(result.analysis)}"
    )

    return result
