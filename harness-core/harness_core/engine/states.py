"""L3 调度内核 - Loop Engine 状态定义（FSM）。

P2 增强版：在 P1 线性链路基础上增加
- REFLECT：每轮自我反思，决定继续 / 重试 / 终止
- VERIFY：结果校验（评测）
- PAUSE：人工介入挂起点（断点续跑的基础）
转移表支持"守卫条件 -> 下一态"的多分支，由 handler 返回决策。
"""
from __future__ import annotations

from enum import Enum


class State(str, Enum):
    PLAN = "PLAN"            # 规划子任务
    TOOL_CALL = "TOOL_CALL"  # 调用工具/模型
    OBSERVE = "OBSERVE"      # 观察结果
    REFLECT = "REFLECT"      # 反思：是否满意 / 是否需重试
    VERIFY = "VERIFY"        # 校验结果质量
    PAUSE = "PAUSE"          # 人工介入挂起
    END = "END"              # 终止


# 守卫决策名 -> 含义（handler 返回这些字符串驱动转移）
class Guard(str, Enum):
    CONTINUE = "continue"   # 继续主链路
    RETRY = "retry"         # 回到 TOOL_CALL 重做
    SATISFIED = "satisfied" # 满意，结束
    NEEDS_HUMAN = "human"   # 需要人工介入
    FAIL = "fail"           # 失败终止


# 状态转移表：当前态 -> {守卫决策: 下一态}
TRANSITIONS: dict[State, dict[str, State]] = {
    State.PLAN: {Guard.CONTINUE: State.TOOL_CALL},
    State.TOOL_CALL: {Guard.CONTINUE: State.OBSERVE},
    State.OBSERVE: {Guard.CONTINUE: State.REFLECT},
    State.REFLECT: {
        Guard.RETRY: State.TOOL_CALL,     # 不满意，重做
        Guard.CONTINUE: State.VERIFY,    # 满意，进入校验
        Guard.NEEDS_HUMAN: State.PAUSE,  # 需人工
    },
    State.VERIFY: {
        Guard.SATISFIED: State.END,      # 校验通过
        Guard.RETRY: State.TOOL_CALL,     # 校验不通过，重做
        Guard.NEEDS_HUMAN: State.PAUSE,
    },
    State.PAUSE: {Guard.CONTINUE: State.VERIFY},  # resume 后继续校验
    State.END: {},
}
