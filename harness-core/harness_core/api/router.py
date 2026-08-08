"""API 层 - 业务路由。

P2 暴露：
- POST /generate/testcase   用例生成（增强引擎 + Trace）
- POST /rag/qa             RAG 问答（新插件，证明横向扩展）
- POST /eval/judge         LLM-as-Judge 评测
- GET  /traces/{trace_id}  全链路 Trace 查询
- GET  /plugins            已注册插件列表

调用规范：所有请求统一经插件机制，不直连模型（红线 #1）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter

from harness_core.api.schemas import (
    EvalRequest, EvalResponse, GenerateRequest, GenerateResponse,
    RagRequest, RagResponse,
)
from harness_core.eval.judge import judge
from harness_core.logging import logger
from harness_core.plugins import PluginContext, get_plugin
from harness_core.trace.store import get_tracer

router = APIRouter(tags=["plugins"])


async def _run_plugin(key: str, ctx: PluginContext, payload: dict):
    plugin_cls = get_plugin(key)
    if plugin_cls is None:
        return None
    return await plugin_cls().execute(ctx, payload)


@router.post("/generate/testcase", response_model=GenerateResponse)
async def generate_testcase(req: GenerateRequest) -> GenerateResponse:
    ctx = PluginContext(
        tenant_id=req.tenant_id, agent_id=req.agent_id or 0,
        model=req.model, trace_id=uuid.uuid4().hex[:16],
    )
    logger.info(f"[API] 用例生成 trace={ctx.trace_id} tenant={req.tenant_id}")
    result = await _run_plugin("testcase_gen", ctx, {"requirement": req.requirement})
    if result is None:
        return GenerateResponse(success=False, error="插件 testcase_gen 未注册")
    if not result.success:
        return GenerateResponse(success=False, error=result.error)
    d = result.data or {}
    return GenerateResponse(
        success=True, trace_id=d.get("trace_id"), requirement=d.get("requirement"),
        cases=d.get("cases", []), final_state=d.get("final_state"),
        paused=d.get("paused", False), pause_reason=d.get("pause_reason"),
    )


@router.post("/rag/qa", response_model=RagResponse)
async def rag_qa(req: RagRequest) -> RagResponse:
    ctx = PluginContext(
        tenant_id=req.tenant_id, agent_id=req.agent_id or 0,
        model=req.model, trace_id=uuid.uuid4().hex[:16],
    )
    logger.info(f"[API] RAG 问答 trace={ctx.trace_id} tenant={req.tenant_id}")
    result = await _run_plugin("rag_qa", ctx, {"question": req.question, "context": req.context})
    if result is None:
        return RagResponse(success=False, error="插件 rag_qa 未注册")
    if not result.success:
        return RagResponse(success=False, error=result.error)
    d = result.data or {}
    return RagResponse(
        success=True, question=d.get("question"), answer=d.get("answer"),
        retrieved=d.get("retrieved", []), trace_id=d.get("trace_id"),
    )


@router.post("/eval/judge", response_model=EvalResponse)
async def eval_judge(req: EvalRequest) -> EvalResponse:
    verdict = await judge(
        tenant_id=req.tenant_id, task=req.task, output=req.output, model=req.model
    )
    return EvalResponse(
        coverage=verdict.get("coverage", 0),
        clarity=verdict.get("clarity", 0),
        executability=verdict.get("executability", 0),
        score=verdict.get("score", 0.0),
        summary=verdict.get("summary", ""),
    )


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> dict:
    tracer = get_tracer(trace_id)
    if tracer is None:
        return {"trace_id": trace_id, "found": False}
    return {"trace_id": trace_id, "found": True, **tracer.summary()}


@router.get("/plugins")
async def list_registered() -> dict:
    from harness_core.plugins import list_plugins

    return {"plugins": list_plugins()}
