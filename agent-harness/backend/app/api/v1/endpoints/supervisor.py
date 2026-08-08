"""
Supervisor-Worker 多代理编排 API 端点

区别于 /workflow：
- /workflow 是单编排（Plan→Orchestrate→Verify，步骤由 template 固定）
- /supervisor 是编排者模式：LLM 实时解析任务 → 动态挑选/跳过/串行/并行 Worker
  → 依据中间结果决定是否追加 Worker（迭代式任务分解），天然支持多 LLM + 多租户偏好
"""
import json
import os
import uuid

from fastapi import APIRouter, Depends, Request, Body, status
from fastapi.responses import StreamingResponse, JSONResponse

from app.schemas.supervisor import SupervisorStreamRequest, SupervisorInvokeRequest
from app.core.workflow import run_supervisor_stream, run_supervisor_sync
from app.core.auth import JWTUser, get_current_user
from app.core.telemetry import get_tracer

router = APIRouter()
tracer = get_tracer(__name__)


def _resolve_auth_token(request: Request | None, request_auth_token: str | None = None) -> str | None:
    """同 workflow 端点：优先 Authorization header，其次请求体，最后服务令牌"""
    if request is not None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and len(auth_header) > 7:
            return auth_header[7:]
    if request_auth_token:
        return request_auth_token
    return os.getenv("SERVICE_TOKEN")


@router.post("/stream")
async def supervisor_stream(
    request: SupervisorStreamRequest = Body(...),
    raw_request: Request = None,
    user: JWTUser = Depends(get_current_user),
):
    """SSE 流式 Supervisor-Worker 编排入口（支持 supervisor_plan_* / supervisor_worker_* 事件）"""
    task_id = request.task_id or str(uuid.uuid4())[:12]
    resolved_token = _resolve_auth_token(raw_request, request.auth_token)

    def generate():
        for event in run_supervisor_stream(
            user_request=request.user_request,
            task_id=task_id,
            user_id=request.user_id,
            auth_token=resolved_token,
            team_id=request.team_id or "default",
            template_id=request.template_id,
            model=request.model,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Task-ID": task_id,
        },
    )


@router.post("/invoke")
async def supervisor_invoke(
    request: SupervisorInvokeRequest = Body(...),
    raw_request: Request = None,
    user: JWTUser = Depends(get_current_user),
):
    """同步 Supervisor-Worker 编排入口（返回完整编排结果）"""
    task_id = request.task_id or str(uuid.uuid4())[:12]
    resolved_token = _resolve_auth_token(raw_request, request.auth_token)

    try:
        with tracer.start_as_current_span("supervisor.invoke_sync") as span:
            span.set_attribute("task_id", task_id)
            span.set_attribute("team_id", request.team_id or "default")
            result = run_supervisor_sync(
                user_request=request.user_request,
                task_id=task_id,
                user_id=request.user_id,
                auth_token=resolved_token,
                team_id=request.team_id or "default",
                template_id=request.template_id,
                model=request.model,
            )
        return result
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"task_id": task_id, "status": "failed", "error": str(e)},
        )
