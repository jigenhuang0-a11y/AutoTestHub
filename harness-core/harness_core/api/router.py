"""API 层 - 业务路由。

P1 暴露：用例生成接口（端到端演示链路）。
调用规范：所有请求统一经插件机制，不直连模型（红线 #1）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter

from harness_core.api.schemas import GenerateRequest, GenerateResponse
from harness_core.logging import logger
from harness_core.plugins import PluginContext, get_plugin

router = APIRouter(tags=["plugins"])


@router.post("/generate/testcase", response_model=GenerateResponse)
async def generate_testcase(req: GenerateRequest) -> GenerateResponse:
    plugin_cls = get_plugin("testcase_gen")
    if plugin_cls is None:
        return GenerateResponse(success=False, error="插件 testcase_gen 未注册")

    plugin = plugin_cls()
    ctx = PluginContext(
        tenant_id=req.tenant_id,
        agent_id=req.agent_id or 0,
        model=req.model,
        trace_id=uuid.uuid4().hex[:16],
    )
    logger.info(f"[API] 用例生成请求 trace={ctx.trace_id} tenant={req.tenant_id}")
    result = await plugin.execute(ctx, {"requirement": req.requirement})
    if not result.success:
        return GenerateResponse(success=False, error=result.error)
    data = result.data or {}
    return GenerateResponse(
        success=True,
        trace_id=data.get("trace_id"),
        requirement=data.get("requirement"),
        cases=data.get("cases", []),
    )


@router.get("/plugins", summary="已注册插件列表")
async def list_registered() -> dict:
    from harness_core.plugins import list_plugins

    return {"plugins": list_plugins(), "tools": []}
