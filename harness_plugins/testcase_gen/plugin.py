"""测试用例生成插件（P2 升级：接入增强版 Loop Engine + Trace）。

链路：PLAN -> TOOL_CALL -> OBSERVE -> REFLECT -> VERIFY -> END
- REFLECT：LLM 自评生成质量，不满意回退 TOOL_CALL 重做（最多 1 次）
- VERIFY：结构化校验（JSON 合法性 + 用例条数），不通过回退重做
- PAUSE：若 REFLECT 判定需人工确认，则挂起等待 resume
全程只通过 harness_core 中台原语调用（红线 #1）。
"""
from __future__ import annotations

import json

from harness_core.engine.loop import LoopEngine
from harness_core.engine.states import Guard, State
from harness_core.llm.base import ChatMessage
from harness_core.llm.gateway import GatewayContext, gateway
from harness_core.plugins import (
    BasePlugin,
    PluginContext,
    PluginResult,
    register_plugin,
)
from harness_core.trace.store import new_tracer

_SYSTEM_PROMPT = (
    "你是一名资深测试开发工程师。根据用户给出的需求描述，"
    "生成结构化测试用例，每条包含：标题、前置条件、步骤、预期结果。"
    "只输出 JSON 数组，不要附加解释。"
)

_REFLECT_PROMPT = (
    "你是一名测试架构师。请审核下列测试用例是否覆盖了需求的关键场景。"
    "只回答 JSON：{\"satisfied\": true/false, \"need_human\": true/false, \"reason\": \"...\"}"
)


def _build_engine(tracer) -> LoopEngine:
    engine = LoopEngine(tracer=tracer)

    @engine.on(State.PLAN)
    async def plan(ctx: object) -> tuple[Guard, dict]:
        ctx.memory["requirement"] = ctx.memory.get("requirement", "")
        ctx.memory.setdefault("retry_count", 0)
        return Guard.CONTINUE, {"planned": True}

    @engine.on(State.TOOL_CALL)
    async def tool_call(ctx: object) -> tuple[Guard, dict]:
        gctx: GatewayContext = ctx.memory["gateway_ctx"]
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=ctx.memory["requirement"]),
        ]
        resp = await gateway.chat(gctx, messages, temperature=0.4, max_tokens=2048)
        ctx.memory["raw"] = resp.content
        return Guard.CONTINUE, {"called": True}

    @engine.on(State.OBSERVE)
    async def observe(ctx: object) -> tuple[Guard, dict]:
        raw = ctx.memory.get("raw", "")
        try:
            cases = json.loads(raw)
            ctx.memory["cases"] = cases
            return Guard.CONTINUE, {"valid": True, "count": len(cases)}
        except (json.JSONDecodeError, TypeError):
            ctx.memory["cases"] = []
            return Guard.CONTINUE, {"valid": False}

    @engine.on(State.REFLECT)
    async def reflect(ctx: object) -> tuple[Guard, dict]:
        if not ctx.memory.get("cases"):
            # 生成失败，直接重做（限 1 次避免死循环）
            if ctx.memory["retry_count"] < 1:
                ctx.memory["retry_count"] += 1
                return Guard.RETRY, {"reason": "parse-failed"}
            return Guard.NEEDS_HUMAN, {"reason": "多次生成仍无法解析"}

        gctx: GatewayContext = ctx.memory["gateway_ctx"]
        messages = [
            ChatMessage(role="system", content=_REFLECT_PROMPT),
            ChatMessage(role="user", content=json.dumps(ctx.memory["cases"], ensure_ascii=False)),
        ]
        resp = await gateway.chat(gctx, messages, temperature=0.2, max_tokens=512)
        try:
            verdict = json.loads(resp.content)
        except (json.JSONDecodeError, TypeError):
            verdict = {"satisfied": True, "need_human": False}
        if verdict.get("need_human"):
            ctx.pause_reason = verdict.get("reason", "需人工确认")
            return Guard.NEEDS_HUMAN, verdict
        if not verdict.get("satisfied") and ctx.memory["retry_count"] < 1:
            ctx.memory["retry_count"] += 1
            return Guard.RETRY, verdict
        return Guard.CONTINUE, verdict

    @engine.on(State.VERIFY)
    async def verify(ctx: object) -> tuple[Guard, dict]:
        cases = ctx.memory.get("cases", [])
        if len(cases) >= 1:
            return Guard.SATISFIED, {"count": len(cases)}
        if ctx.memory["retry_count"] < 1:
            ctx.memory["retry_count"] += 1
            return Guard.RETRY, {"reason": "cases-empty"}
        return Guard.NEEDS_HUMAN, {"reason": "校验不通过"}

    return engine


@register_plugin
class TestcaseGenPlugin(BasePlugin):
    key = "testcase_gen"
    name = "AI 测试用例生成"
    sandbox_required = False

    async def execute(self, ctx: PluginContext, payload: dict) -> PluginResult:
        requirement = payload.get("requirement", "")
        if not requirement:
            return PluginResult(success=False, error="requirement 不能为空")

        tracer = new_tracer(ctx.trace_id)
        gctx = GatewayContext(
            tenant_id=ctx.tenant_id,
            agent_id=ctx.agent_id,
            trace_id=tracer.trace_id,
            model_preference=ctx.model or "deepseek-chat",
        )
        engine = _build_engine(tracer)
        loop_ctx = await engine.run(
            initial={"requirement": requirement, "gateway_ctx": gctx}
        )
        cases = loop_ctx.memory.get("cases", [])
        return PluginResult(
            success=True,
            data={
                "requirement": requirement,
                "cases": cases,
                "trace_id": tracer.trace_id,
                "final_state": loop_ctx.state.value,
                "paused": loop_ctx.state == State.PAUSE,
                "pause_reason": loop_ctx.pause_reason,
            },
        )
