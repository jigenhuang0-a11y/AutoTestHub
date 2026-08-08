"""L3 调度内核 - Loop Engine（P2 增强版）。

在 P1 基础上：
- handler 返回 (next_decision: Guard, payload)，驱动多分支转移
- 支持 PAUSE 状态：引擎挂起，外界可 resume 并从断点继续（人工介入/断点续跑）
- 支持 checkpoint：引擎状态可序列化落库（P2 内存版，P3 接 MySQL）
- 接入 Tracer：每个状态产生一个 Span，形成全链路 Trace

红线 #3：引擎只负责调度，业务逻辑仍由 handler 提供。
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable, Optional

from harness_core.engine.states import Guard, State, TRANSITIONS
from harness_core.logging import logger
from harness_core.trace.span import Span, Tracer
from harness_core.trace.store import new_tracer

# handler 返回类型：(转移决策, 该态产出)
StepResult = tuple[Guard, Any]

StepHandler = Callable[["LoopContext"], Awaitable[StepResult]]


@dataclass
class LoopContext:
    trace_id: str
    state: State = State.PLAN
    memory: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    # PAUSE 挂起原因（人工介入展示用）
    pause_reason: Optional[str] = None


@dataclass
class LoopCheckpoint:
    """可序列化引擎快照，用于断点续跑。"""
    trace_id: str
    state: str
    memory: dict[str, Any]
    pause_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class LoopEngine:
    def __init__(self, tracer: Tracer | None = None) -> None:
        self._handlers: dict[State, StepHandler] = {}
        self.tracer = tracer or new_tracer()

    def on(self, state: State) -> Callable[[StepHandler], StepHandler]:
        def deco(handler: StepHandler) -> StepHandler:
            self._handlers[state] = handler
            return handler

        return deco

    async def run(
        self, initial: dict[str, Any] | None = None, *, max_steps: int = 32
    ) -> LoopContext:
        ctx = LoopContext(trace_id=self.tracer.trace_id)
        if initial:
            ctx.memory.update(initial)
        return await self._drive(ctx, max_steps=max_steps)

    async def _drive(self, ctx: LoopContext, *, max_steps: int) -> LoopContext:
        steps = 0
        while ctx.state != State.END and steps < max_steps:
            if ctx.state == State.PAUSE:
                # 挂起：等待外部 resume，不再自动推进
                logger.info(f"[LoopEngine] trace={ctx.trace_id} 挂起于 PAUSE: {ctx.pause_reason}")
                return ctx

            handler = self._handlers.get(ctx.state)
            if handler is None:
                logger.error(f"[LoopEngine] 未注册状态处理器: {ctx.state}")
                break

            span = self.tracer.start(kind=ctx.state.lower(), name=ctx.state.value)
            logger.info(f"[LoopEngine] trace={ctx.trace_id} state={ctx.state}")
            try:
                decision, payload = await handler(ctx)
            except Exception as e:  # noqa: BLE001
                span.finish(status="error", error=str(e))
                logger.exception(f"[LoopEngine] handler 异常 state={ctx.state}")
                ctx.state = State.END
                break
            span.finish(status="ok")

            ctx.result = payload
            ctx.state = self._next(ctx.state, decision)
            steps += 1

        logger.info(f"[LoopEngine] trace={ctx.trace_id} 结束于 {ctx.state}")
        return ctx

    def _next(self, state: State, decision: Guard) -> State:
        mapping = TRANSITIONS.get(state, {})
        if decision not in mapping:
            logger.warning(f"[LoopEngine] 状态 {state} 无守卫 {decision}，按默认结束")
            return State.END
        return mapping[decision]

    def checkpoint(self, ctx: LoopContext) -> LoopCheckpoint:
        return LoopCheckpoint(
            trace_id=ctx.trace_id,
            state=ctx.state.value,
            memory=ctx.memory,
            pause_reason=ctx.pause_reason,
        )

    async def resume(
        self, ctx: LoopContext, *, decision: Guard = Guard.CONTINUE, max_steps: int = 32
    ) -> LoopContext:
        """从 PAUSE 恢复执行。"""
        logger.info(f"[LoopEngine] trace={ctx.trace_id} 从 PAUSE 恢复 decision={decision}")
        ctx.state = self._next(State.PAUSE, decision)
        return await self._drive(ctx, max_steps=max_steps)
