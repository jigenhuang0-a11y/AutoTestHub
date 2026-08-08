"""测试用例生成插件（P1 实装：接入统一模型底座 + Loop Engine）。

链路：PLAN(组织需求) -> TOOL_CALL(调 LLM 生成用例) -> OBSERVE(护栏校验) -> END
全程只通过 harness_core 中台原语调用，不直连第三方 API（红线 #1）。
"""
from __future__ import annotations

from harness_core.engine.loop import LoopEngine
from harness_core.engine.states import State
from harness_core.llm.base import ChatMessage
from harness_core.llm.gateway import GatewayContext, gateway
from harness_core.plugins import (
    BasePlugin,
    PluginContext,
    PluginResult,
    register_plugin,
)

_SYSTEM_PROMPT = (
    "你是一名资深测试开发工程师。根据用户给出的需求描述，"
    "生成结构化测试用例，每条包含：标题、前置条件、步骤、预期结果。"
    "只输出 JSON 数组，不要附加解释。"
)


def _build_engine() -> LoopEngine:
    engine = LoopEngine()

    @engine.on(State.PLAN)
    async def plan(ctx):
        ctx.memory["requirement"] = ctx.memory.get("requirement", "")
        return {"planned": True}

    @engine.on(State.TOOL_CALL)
    async def tool_call(ctx):
        gctx = ctx.memory["gateway_ctx"]
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=ctx.memory["requirement"]),
        ]
        resp = await gateway.chat(gctx, messages, temperature=0.4, max_tokens=2048)
        ctx.memory["raw"] = resp.content
        return resp

    @engine.on(State.OBSERVE)
    async def observe(ctx):
        raw = ctx.memory.get("raw", "")
        # 简单校验：尝试解析 JSON 数组
        import json

        try:
            cases = json.loads(raw)
            ctx.memory["cases"] = cases
            return {"valid": True, "count": len(cases)}
        except (json.JSONDecodeError, TypeError):
            ctx.memory["cases"] = []
            return {"valid": False, "raw": raw}

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

        gctx = GatewayContext(
            tenant_id=ctx.tenant_id,
            agent_id=ctx.agent_id,
            trace_id=ctx.trace_id,
            model_preference=ctx.model or "deepseek-chat",
        )
        engine = _build_engine()
        loop_ctx = await engine.run(
            initial={"requirement": requirement, "gateway_ctx": gctx}
        )
        cases = loop_ctx.memory.get("cases", [])
        return PluginResult(
            success=True,
            data={
                "requirement": requirement,
                "cases": cases,
                "trace_id": loop_ctx.trace_id,
            },
        )
