import json
import os
import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse, JSONResponse

from app.schemas.workflow import (
    WorkflowInvokeRequest,
    WorkflowStreamRequest,
    WorkflowResumeRequest,
    CheckpointResponse,
    ResumeCheckpointResponse,
    RetryStepResponse,
)
from app.core.workflow import (
    run_workflow_stream, build_default_workflow,
    _build_initial_state, _execute_single_step,
)
from app.core.state import WorkflowProgress, ProgressEvent
from app.core.checkpoint import (
    load_checkpoint, save_checkpoint, cleanup_checkpoint,
    cleanup_orphan_checkpoints, record_step_retry,
    MAX_STEP_RETRIES, MAX_GLOBAL_RETRIES,
)
from app.core.metrics import workflow_total
from app.core.telemetry import get_tracer
from app.core.auth import JWTUser, get_current_user, SERVICE_AUTH_PREFIX

router = APIRouter()
tracer = get_tracer(__name__)


def _ensure_task_id(task_id: str | None) -> str:
    return task_id or str(uuid.uuid4())[:12]


def _resolve_auth_token(request: Request, request_auth_token: str | None = None) -> str | None:
    """
    解析认证令牌，供工作流下游调用本地工具层。

    优先级：
    1. 中间件已验证的 JWT（从 Authorization: Bearer header 提取原始 token）
    2. 请求体内的 auth_token（向后兼容旧调用方式）
    3. 环境变量 SERVICE_TOKEN（服务间通行）
    """
    # 优先：从中间件已验证的 Authorization header 提取原始 JWT
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and len(auth_header) > 7:
        return auth_header[7:]

    # 兜底：请求体内的 auth_token
    if request_auth_token:
        return request_auth_token

    # 最后兜底：服务间通行令牌
    return os.getenv("SERVICE_TOKEN")


@router.post("/invoke")
async def workflow_invoke(
    request: WorkflowInvokeRequest,
    raw_request: Request,
    user: JWTUser = Depends(get_current_user),
):
    """同步工作流执行入口（支持传入 task_id 断点续跑）"""
    task_id = _ensure_task_id(request.task_id)
    workflow_total.labels(status="started", mode="sync").inc()

    try:
        with tracer.start_as_current_span("workflow.invoke_sync") as span:
            span.set_attribute("task_id", task_id)
            span.set_attribute("auth_method", user.auth_method)
            span.set_attribute("user_id", user.user_id)

            resolved_token = _resolve_auth_token(raw_request, request.auth_token)

            # 检查是否有 checkpoint 可恢复
            cp = load_checkpoint(task_id)
            if cp and cp.state:
                # 从 checkpoint 恢复
                span.set_attribute("resume", True)
                span.set_attribute("resume_phase", cp.phase)
                initial_state = _build_initial_state(
                    user_request=request.user_request,
                    task_id=task_id,
                    user_id=request.user_id,
                    auth_token=resolved_token,
                    progress_callback=None,
                    team_id=request.team_id or "default",
                    template_id=request.template_id,
                )
            else:
                initial_state = {
                    "user_request": request.user_request,
                    "task_id": task_id,
                    "user_id": request.user_id,
                    "team_id": request.team_id or "default",
                    "template_id": request.template_id,
                    "auth_token": resolved_token,
                    "context": {},
                    "_completed_steps": [],
                    "_retry_count": 0,
                    "_step_retry_counts": {},
                }

            workflow = build_default_workflow(use_parallel=True)
            final_state = workflow.invoke(initial_state)
            workflow_total.labels(status="completed", mode="sync").inc()
            cleanup_checkpoint(task_id)

        return {
            "task_id": task_id,
            "status": "completed",
            "plan": final_state.get("plan", []),
            "results": final_state.get("results", []),
            "verification": final_state.get("verification", {}),
        }

    except Exception as e:
        workflow_total.labels(status="failed", mode="sync").inc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"task_id": task_id, "status": "failed", "error": str(e)},
        )


@router.post("/stream")
async def workflow_stream(
    request: WorkflowStreamRequest,
    raw_request: Request,
    user: JWTUser = Depends(get_current_user),
):
    """SSE 流式工作流执行入口（支持传入 task_id 断点续跑）"""
    task_id = _ensure_task_id(request.task_id)

    resolved_token = _resolve_auth_token(raw_request, request.auth_token)

    def generate():
        for event in run_workflow_stream(
            user_request=request.user_request,
            task_id=task_id,
            user_id=request.user_id,
            auth_token=resolved_token,
            team_id=request.team_id or "default",
            template_id=request.template_id,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    response = StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Task-ID": task_id,
        },
    )
    return response


@router.post("/resume/{task_id}", response_model=ResumeCheckpointResponse)
async def workflow_resume(
    task_id: str,
    request: WorkflowResumeRequest,
    raw_request: Request,
    user: JWTUser = Depends(get_current_user),
):
    """
    专用断点续跑端点

    1. 加载 checkpoint
    2. 校验版本兼容性
    3. 从断点阶段继续执行
    4. 返回 SSE 流式结果
    """
    cp = load_checkpoint(task_id)
    if not cp:
        return ResumeCheckpointResponse(
            task_id=task_id,
            resumed=False,
            phase="unknown",
            message="未找到该任务的 checkpoint",
        )

    if not cp.is_compatible():
        return ResumeCheckpointResponse(
            task_id=task_id,
            resumed=False,
            phase=cp.phase,
            message=f"Checkpoint 版本不兼容 (v{cp.version}, 当前 v{cp.version})",
        )

    # 检查重试上限
    if cp.retry_count >= MAX_GLOBAL_RETRIES:
        return ResumeCheckpointResponse(
            task_id=task_id,
            resumed=False,
            phase=cp.phase,
            message=f"重试已达上限 ({MAX_GLOBAL_RETRIES})，无法继续恢复",
            retry_count=cp.retry_count,
        )

    def generate():
        from app.core.workflow import run_workflow_stream
        user_request = request.user_request or cp.state.get("user_request", "")
        resolved_token = _resolve_auth_token(raw_request, request.auth_token)

        for event in run_workflow_stream(
            user_request=user_request,
            task_id=task_id,
            user_id=request.user_id or cp.state.get("user_id"),
            auth_token=resolved_token or cp.state.get("auth_token"),
            team_id=request.team_id or cp.state.get("team_id", "default"),
            template_id=request.template_id,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Task-ID": task_id,
            "X-Resume": "true",
            "X-Resume-Phase": cp.phase,
        },
    )


@router.post("/retry-step/{task_id}/{step_index}", response_model=RetryStepResponse)
async def workflow_retry_step(
    task_id: str,
    step_index: int,
    user: JWTUser = Depends(get_current_user),
):
    """
    重试单个失败步骤

    1. 加载 checkpoint
    2. 定位失败步骤
    3. 单步重试（含自愈）
    4. 更新 checkpoint
    """
    cp = load_checkpoint(task_id)
    if not cp:
        return RetryStepResponse(
            task_id=task_id,
            step_index=step_index,
            retried=False,
            message="未找到该任务的 checkpoint",
        )

    plan = cp.state.get("plan", [])
    if step_index < 0 or step_index >= len(plan):
        return RetryStepResponse(
            task_id=task_id,
            step_index=step_index,
            retried=False,
            message=f"步骤 {step_index} 不存在（计划共 {len(plan)} 步）",
        )

    # 检查单步重试上限
    step_retries = cp.step_retry_counts.get(step_index, 0)
    if step_retries >= MAX_STEP_RETRIES:
        return RetryStepResponse(
            task_id=task_id,
            step_index=step_index,
            retried=False,
            message=f"步骤 {step_index} 重试已达上限 ({MAX_STEP_RETRIES})",
            retry_count=step_retries,
        )

    step = plan[step_index]
    state = dict(cp.state)
    state["task_id"] = task_id

    try:
        result = _execute_single_step(step, state)
        record_step_retry(task_id, step_index)

        # 更新 step 结果到 results 列表
        results = list(cp.state.get("results") or [])
        replaced = False
        for i, r in enumerate(results):
            if r.get("step_index") == step_index:
                results[i] = result
                replaced = True
                break
        if not replaced:
            results.append(result)

        state["results"] = results

        # 保存更新后的 checkpoint
        completed = list(cp.completed_steps or [])
        if result.get("status") == "completed":
            completed.append(step_index)
        save_checkpoint(state, phase=cp.phase, completed_steps=completed)

        return RetryStepResponse(
            task_id=task_id,
            step_index=step_index,
            retried=True,
            status=result.get("status", "unknown"),
            result=result.get("result"),
            retry_count=step_retries + 1,
        )

    except Exception as e:
        record_step_retry(task_id, step_index)
        new_count = step_retries + 1
        return RetryStepResponse(
            task_id=task_id,
            step_index=step_index,
            retried=False,
            status="failed",
            message=str(e),
            retry_count=new_count,
        )


@router.get("/progress/{task_id}")
async def workflow_progress(
    task_id: str,
    user: JWTUser = Depends(get_current_user),
):
    """查询工作流进度"""
    progress = WorkflowProgress.get(task_id)
    if not progress:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"exists": False, "message": "任务未找到或已过期"},
        )
    return {"exists": True, "progress": progress}


@router.get("/checkpoint/{task_id}", response_model=CheckpointResponse)
async def workflow_checkpoint(
    task_id: str,
    user: JWTUser = Depends(get_current_user),
):
    """查询 checkpoint 状态（用于断点续跑前确认进度）"""
    cp = load_checkpoint(task_id)
    if not cp:
        return CheckpointResponse(task_id=task_id, exists=False)

    state = cp.state
    return CheckpointResponse(
        task_id=task_id,
        exists=True,
        phase=cp.phase,
        current_step=state.get("current_step"),
        total_steps=len(state.get("plan", [])),
        completed_steps=cp.completed_steps,
        retry_count=cp.retry_count,
        step_retry_counts=cp.step_retry_counts,
        created_at=cp.created_at,
        compatible=cp.is_compatible(),
    )


@router.post("/checkpoint/cleanup")
async def workflow_cleanup_orphans(
    user: JWTUser = Depends(get_current_user),
):
    """手动触发孤儿 checkpoint 清理"""
    cleaned = cleanup_orphan_checkpoints()
    return {"cleaned": cleaned, "message": f"已清理 {cleaned} 个孤儿 checkpoint"}
