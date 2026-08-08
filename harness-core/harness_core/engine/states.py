"""L3 调度内核 - Loop Engine 状态定义（FSM）。

P1 最简 MVP：PLAN -> TOOL_CALL -> OBSERVE -> END
（REFLECT / 分支 / 人机介入 / checkpoint 在 P2 增强）

状态机设计要点（简历卖点）：
- 状态转移显式、可审计、可持久化（P2）
- 守卫条件(guard)决定转移，不在业务里硬编码循环
"""
from __future__ import annotations

from enum import Enum


class State(str, Enum):
    PLAN = "PLAN"          # 规划子任务
    TOOL_CALL = "TOOL_CALL"  # 调用工具/模型
    OBSERVE = "OBSERVE"    # 观察结果
    END = "END"            # 终止


# 状态转移表：当前态 -> {(守卫条件名): 下一态}
# P1 线性：(PLAN -> TOOL_CALL -> OBSERVE -> END)
TRANSITIONS: dict[State, dict[str, State]] = {
    State.PLAN: {"default": State.TOOL_CALL},
    State.TOOL_CALL: {"default": State.OBSERVE},
    State.OBSERVE: {"default": State.END},
    State.END: {},
}
