"""Multi-Agent 用例生成插件（P3 新增，证明编排者-工作者协作）。

Orchestrator 拆解目标 -> planner 设计框架 -> generator 生成用例 -> reviewer 审查补充。
全程经统一模型底座，不直连第三方（红线 #1）。
"""
from __future__ import annotations

import json

from harness_core.engine.orchestrator import Orchestrator, SubTask
from harness_core.llm.base import ChatMessage
from harness_core.llm.gateway import GatewayContext, gateway
from harness_core.plugins import (
    BasePlugin, PluginContext, PluginResult, register_plugin,
)


async def _planner(gctx: GatewayContext, st: SubTask) -> str:
    resp = await gateway.chat(gctx, [
        ChatMessage(role="system", content="你是测试架构师，输出用例设计框架（维度/场景分类）。"),
        ChatMessage(role="user", content=st.description),
    ], temperature=0.4)
    return resp.content


async def _generator(gctx: GatewayContext, st: SubTask) -> str:
    resp = await gateway.chat(gctx, [
        ChatMessage(role="system", content="你是测试工程师，基于框架生成 JSON 用例数组，每项含标题/步骤/预期。"),
        ChatMessage(role="user", content=st.description),
    ], temperature=0.4)
    return resp.content


async def _reviewer(gctx: GatewayContext, st: SubTask) -> str:
    resp = await gateway.chat(gctx, [
        ChatMessage(role="system", content="你是测试审查员，检查用例覆盖率并补充缺失场景（简洁）。"),
        ChatMessage(role="user", content=st.description),
    ], temperature=0.3)
    return resp.content


@register_plugin
class TestcaseGenMultiPlugin(BasePlugin):
    key = "testcase_gen_multi"
    name = "Multi-Agent 用例生成"
    sandbox_required = False

    async def execute(self, ctx: PluginContext, payload: dict) -> PluginResult:
        goal = payload.get("requirement", "")
        if not goal:
            return PluginResult(success=False, error="requirement 不能为空")
        gctx = GatewayContext(
            tenant_id=ctx.tenant_id, agent_id=ctx.agent_id,
            trace_id=ctx.trace_id, model_preference=ctx.model or "deepseek-chat",
        )
        orch = Orchestrator()
        orch.register_worker("planner", _planner)
        orch.register_worker("generator", _generator)
        orch.register_worker("reviewer", _reviewer)
        result = await orch.run(gctx, goal)
        # 尝试从 generator 结果解析用例数
        case_count = 0
        for st in result.subtasks:
            if st.assignee == "generator":
                try:
                    case_count = len(json.loads(st.result))
                except Exception:
                    case_count = st.result.count("标题")
        return PluginResult(success=True, data={
            "requirement": goal,
            "final": result.final,
            "subtasks": [{"assignee": s.assignee, "status": s.status, "result": s.result} for s in result.subtasks],
            "case_count": case_count,
            "trace_id": result.trace_id,
        })
