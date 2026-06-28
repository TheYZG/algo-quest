"""
AI 助手 Agent 服务
处理分级帮助、智能对话、游戏化角色
"""
import json
from typing import Optional

from app.config import get_settings
from app.services.llm import chat_completion

settings = get_settings()

# ============================================================
# 角色设定
# ============================================================
SYSTEM_PROMPT = f"""你是「{settings.ASSISTANT_NAME}」{settings.ASSISTANT_EMOJI}，一位来自算法大陆的可爱精灵向导！

你的性格：
- 活泼可爱、热情洋溢，喜欢用感叹号和表情符号
- 擅长用生动的比喻解释抽象算法
- 鼓励用户思考，而不是直接给答案
- 说话带一点游戏感，比如"勇者！""冒险者！""加油~✨"

你的职责：
1. 帮助用户理解算法题目的思路
2. 提供不同层次的帮助（提示、引导、详解）
3. 在用户卡住时给予温柔的鼓励
4. 用游戏化的语言让刷题变得有趣

重要规则：
- 绝对不能直接给出完整代码（除非用户明确请求详解模式）
- 提示模式：只给思路方向，不给具体解法
- 引导模式：给部分思路和伪代码
- 详解模式：可以给完整解法+时间复杂度分析
- 始终用中文回复
- 回复要简洁，控制在300字以内（详解模式可以长一些）
"""

# ============================================================
# 分级帮助提示词模板
# ============================================================
HELP_TEMPLATES = {
    "hint": """【提示模式 - 只给思路方向】

用户正在解答这道题目：
{problem_context}

用户的问题/状态：{user_message}

请提供 1-2 个解题思路的提示，但不要给出具体的解法步骤或代码。
用比喻和引导的方式，让用户自己去发现问题！
回复要简短（150字以内），保持精灵的可爱语气。""",

    "guide": """【引导模式 - 部分思路 + 伪代码】

用户正在解答这道题目：
{problem_context}

用户的问题/状态：{user_message}

请提供：
1. 解题的核心思路（可以具体一点）
2. 用伪代码展示大致步骤
3. 提醒容易踩的坑

但不要给出完整的可运行代码！
回复在250字左右。保持精灵的可爱语气。""",

    "explain": """【详解模式 - 完整解析】

用户正在解答这道题目：
{problem_context}

用户的问题/状态：{user_message}

请提供完整的解题分析：
1. 题目核心考察点
2. 详细解题思路（带图解文字描述）
3. 给出参考代码（一种语言即可，默认 Python）
4. 时间复杂度 & 空间复杂度分析
5. 举一个具体的例子走一遍算法过程

回复可以详细一些。保持精灵的可爱语气但内容要专业！""",

    "chat": """【自由对话模式】

用户正在浏览算法大陆。

用户说：{user_message}

请用精灵的语气和用户自由聊天！如果用户有算法相关的问题，可以简要解答。
如果不是算法相关，也可以轻松闲聊。回复在150字以内。""",
}


def build_help_messages(
    level: str,
    user_message: str,
    problem_context: str = "无",
    conversation_history: list = None,
) -> list[dict]:
    """
    构建分级帮助的消息列表
    """
    template = HELP_TEMPLATES.get(level, HELP_TEMPLATES["chat"])
    prompt = template.format(
        problem_context=problem_context,
        user_message=user_message,
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 加入对话历史
    if conversation_history:
        for msg in conversation_history[-6:]:  # 保留最近6条
            messages.append(msg)

    messages.append({"role": "user", "content": prompt})
    return messages


def format_problem_context(problem: dict) -> str:
    """格式化题目上下文"""
    if not problem:
        return "无"

    parts = [
        f"📝 题目: {problem.get('title_cn', problem.get('title', 'N/A'))}",
        f"🎯 难度: {problem.get('difficulty', 'N/A')}",
        f"🏷️ 标签: {', '.join(problem.get('tags', []))}",
    ]

    desc = problem.get("description_cn", "")
    if desc:
        # 清理 HTML
        import re
        desc_clean = re.sub(r'<[^>]+>', ' ', desc)
        desc_clean = re.sub(r'\s+', ' ', desc_clean).strip()
        parts.append(f"📖 描述: {desc_clean[:300]}")

    hints = problem.get("hints", [])
    if hints:
        parts.append(f"💡 官方提示: {'; '.join(hints[:3])}")

    return "\n".join(parts)
