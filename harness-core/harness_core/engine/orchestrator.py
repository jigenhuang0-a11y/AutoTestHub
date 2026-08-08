"""L3 调度内核 - Multi-Agent 编排者-工作者模式（P3）。

Orchestrator（编排者）：
- 接收高层目标，调用 LLM 拆解为若干子任务（DAG）
- 为每个子任务派发一个 Worker Agent（复用 Loop Engine 或插件）
- 汇总各 Worker 结果，做最终整合

与单 Agent 的区别（面试卖点）：
- 关注点分离：规划与执行解耦，可独立扩展 Worker 类型
- 并行潜力：子任务可并发派发（P3 单线程顺序，P4 接异步池）
- 故障隔离：单个 Worker 失败不影响整体，可重试/降级

红线 #3：编排逻辑在引擎内，业务插件只提供执行能力。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from harness_core.llm.base import ChatMessage
from harness_core.llm.gateway import GatewayContext, gateway
from harness_core.logging import logger
from harness_core.trace.store import new_tracer


@dataclass
class SubTask:
    id: str
    description: str
    assignee: str  # worker 类型 key
    result: Any = None
    status: str = "pending"


@dataclass
class OrchestrationResult:
    goal: str
    subtasks: list[SubTask] = field(default_factory=list)
    final: Any = None
    trace_id: str = ""


# worker 执行函数：key -> async (ctx, subtask) -> result
WorkerFn = Callable[[GatewayContext, SubTask], Any]


_PLANNER_PROMPT = (
    "你是一个任务编排者。请将用户目标拆解为 2-4 个可独立执行的子任务。"
    "只输出 JSON 数组，每项：{\"assignee\": \"角色名\", \"description\": \"任务描述\"}。"
    "角色限定为：planner(规划), generator(生成), reviewer(审查), summarizer(总结)。"
)


class Orchestrator:
    def __init__(self) -> None:
        self._workers: dict[str, WorkerFn] = {}

    def register_worker(self, key: str, fn: WorkerFn) -> None:
        self._workers[key] = fn

    async def run(
        self, gctx: GatewayContext, goal: str, *, max_subtasks: int = 4
    ) -> OrchestrationResult:
        tracer = new_tracer(gctx.trace_id)
        span = tracer.start(kind="orchestrate", name="plan", goal=goal)

        # 1. 编排者规划子任务
        msgs = [
            ChatMessage(role="system", content=_PLANNER_PROMPT),
            ChatMessage(role="user", content=goal),
        ]
        resp = await gateway.chat(gctx, msgs, temperature=0.3, max_tokens=1024)
        try:
            raw = json.loads(resp.content)
        except (json.JSONDecodeError, TypeError):
            raw = [{"assignee": "generator", "description": goal}]
        subtasks = [
            SubTask(id=f"st{i}", description=st.get("description", goal), assignee=st.get("assignee", "generator"))
            for i, st in enumerate(raw[:max_subtasks])
        ]
        span.finish(status="ok", subtask_count=len(subtasks))

        # 2. 派发 Worker 执行（P3 顺序执行，P4 可并发）
        for st in subtasks:
            wspan = tracer.start(kind="worker", name=st.assignee, subtask=st.id)
            worker = self._workers.get(st.assignee)
            if worker is None:
                st.status = "no-worker"
                st.result = f"未注册 worker: {st.assignee}"
                wspan.finish(status="error")
                continue
            try:
                st.result = await worker(gctx, st)
                st.status = "done"
                wspan.finish(status="ok")
            except Exception as e:  # noqa: BLE001
                st.status = "error"
                st.result = str(e)
                wspan.finish(status="error", error=str(e))
                logger.error(f"[Orchestrator] worker {st.assignee} 失败: {e}")

        # 3. 汇总
        summary_span = tracer.start(kind="orchestrate", name="summarize")
        parts = [f"[{st.assignee}] {st.result}" for st in subtasks if st.result]
        final = "\n".join(parts)
        summary_span.finish(status="ok")

        return OrchestrationResult(
            goal=goal, subtasks=subtasks, final=final, trace_id=tracer.trace_id
        )
