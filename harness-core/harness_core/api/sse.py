"""API 层 - SSE 流式端点（P3）。

用于监控大屏 / 前端实时展示生成过程。基于 gateway.stream_chat 逐 token 推送。
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from harness_core.api.schemas import GenerateRequest
from harness_core.llm.base import ChatMessage
from harness_core.llm.gateway import GatewayContext, gateway
from harness_core.logging import logger

router = APIRouter(tags=["stream"])


@router.post("/generate/testcase/stream")
async def generate_stream(req: GenerateRequest):
    """SSE 流式生成用例。每收到一个 token 推送一行 data: {...}。"""
    trace_id = uuid.uuid4().hex[:16]
    gctx = GatewayContext(
        tenant_id=req.tenant_id, agent_id=req.agent_id or 0,
        trace_id=trace_id, model_preference=req.model,
    )
    system = (
        "你是一名资深测试开发工程师。根据用户需求生成结构化测试用例，"
        "每条含标题、前置条件、步骤、预期结果。直接输出，无需解释。"
    )

    async def event_gen():
        yield f"data: {json.dumps({'type': 'start', 'trace_id': trace_id}, ensure_ascii=False)}\n\n"
        try:
            async for chunk in gateway.stream_chat(
                gctx,
                [ChatMessage(role="system", content=system),
                 ChatMessage(role="user", content=req.requirement)],
                temperature=0.4, max_tokens=2048,
            ):
                yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            logger.error(f"[SSE] 生成失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'end', 'trace_id': trace_id}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
