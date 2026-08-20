"""图节点通用工具"""
import json
import re


def parse_json_block(text: str) -> dict | None:
    """从 LLM 回复中提取 JSON 对象（容忍 markdown 代码块与前后杂文本）"""
    if not text:
        return None
    # 1. 直接尝试
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    # 2. 提取 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    # 3. 提取首个 {...} 平衡块
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return None
