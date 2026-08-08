"""L3 调度内核 - Loop Engine 最简 MVP。

单线程事件循环驱动 FSM。P1 目标：跑通一条插件业务链路
（PLAN -> TOOL_CALL -> OBSERVE -> END），不依赖 langgraph。

引擎只负责"调度"，具体业务逻辑由传入的 handler 提供，
从而保证红线 #3：业务代码不写死调度逻辑。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from harness_core.engine.states import State, TRANSITIONS
from harness_core.logging import logger

# 每个状态的处理函数签名：接收 engine 当前上下文，返回该态产出
StepHandler = Callable[["LoopContext"], Awaitable[Any]]


@dataclass
class LoopContext:
    trace_id: str
    state: State = State.PLAN
    memory: dict[str, Any] = field(default_factory=dict)
    result: Any = None


class LoopEngine:
    def __init__(self) -> None:
        self._handlers: dict[State, StepHandler] = {}

    def on(self, state: State) -> Callable[[StepHandler], StepHandler]:
        """装饰器用法：@engine.on(State.PLAN)  def plan(ctx): ..."""

        def deco(handler: StepHandler) -> StepHandler:
            self._handlers[state] = handler
            return handler

        return deco

    async def run(
        self, initial: dict[str, Any] | None = None, *, max_steps: int = 16
    ) -> LoopContext:
        ctx = LoopContext(trace_id=uuid.uuid4().hex[:16])
        if initial:
            ctx.memory.update(initial)
        steps = 0
        while ctx.state != State.END and steps < max_steps:
            handler = self._handlers.get(ctx.state)
            if handler is None:
                logger.error(f"[LoopEngine] 未注册状态处理器: {ctx.state}")
                break
            logger.info(f"[LoopEngine] trace={ctx.trace_id} state={ctx.state}")
            ctx.result = await handler(ctx)
            # 状态转移
            guards = TRANSITIONS.get(ctx.state, {})
            ctx.state = guards.get("default", State.END)
            steps += 1
        logger.info(f"[LoopEngine] trace={ctx.trace_id} 结束于 {ctx.state}")
        return ctx
