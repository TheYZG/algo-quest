"""
议会共享状态 — LangGraph 全图流转的 State 定义
所有节点读写同一份 ParliamentState，timeline 记录协作事件流供前端渲染
"""
import time
from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages


class ParliamentState(TypedDict):
    """议会全局状态（total，非 partial——各节点返回增量 dict 由 LangGraph 合并）"""
    messages: Annotated[list, add_messages]   # 对话记忆（checkpointer 持久化）
    user_id: str
    problem_id: Optional[str]
    user_code: Optional[str]                  # 用户当前代码（求助/判题场景）
    language: Optional[str]                   # 提交语言
    intent: Optional[str]                     # Queen 识别的意图
    pinned_level: Optional[str]               # /hint 固定的帮助级别 hint/guide/explain
    current_agent: Optional[str]              # 当前执行的专家
    task_brief: str                           # Queen 派单时下发的任务上下文
    agent_outputs: dict                       # {agent_name: 产出文本}
    judge_result: Optional[dict]              # 判题官结构化裁决
    review_verdict: Optional[dict]            # 复核官结构化裁决
    needs_review: bool                        # 是否触发复核
    final_reply: str                          # 汇总回复
    timeline: list                            # 协作事件流
    coins_to_spend: int                       # API 层注入，图内不修改


def make_timeline_event(
    type: str,
    agent: str,
    action: str,
    duration_ms: int | None = None,
) -> dict:
    """构造一条协作时间线事件"""
    ev = {
        "type": type,        # agent_start / agent_done / arbitrate / final
        "agent": agent,      # queen / tutor / judge / scout / planner / reviewer
        "action": action,
        "ts": time.time(),
    }
    if duration_ms is not None:
        ev["duration_ms"] = duration_ms
    return ev
