"""
多 Agent 团队编排 API

提供团队任务生命周期、交接记录、评审门控的 REST 接口。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.auth import JWTUser, get_current_user
from app.core.task_store import TaskStore
from app.core.team_orchestrator import TeamOrchestrator, get_team_orchestrator
from app.schemas.team import (
    TeamOrchestrateRequest,
    TeamOrchestrateResponse,
    TeamRole,
    TeamTask,
    TeamTaskCreate,
    TeamTaskListResponse,
    TeamTaskStatus,
    TeamTaskUpdate,
)

router = APIRouter(prefix="/team", tags=["team-orchestration"])


def _get_orchestrator(store: TaskStore = Depends(TaskStore)) -> TeamOrchestrator:
    return get_team_orchestrator(store=store)


@router.post(
    "/tasks",
    response_model=TeamTask,
    status_code=status.HTTP_201_CREATED,
    summary="创建团队编排任务",
)
def create_team_task(
    request: Request,
    req: TeamTaskCreate,
    orchestrator: TeamOrchestrator = Depends(_get_orchestrator),
    current_user: JWTUser = Depends(get_current_user),
):
    if not req.user_id:
        req.user_id = str(current_user.user_id) if current_user else ""
    return orchestrator.create_task(req)


@router.get(
    "/tasks",
    response_model=TeamTaskListResponse,
    summary="列出团队任务",
)
def list_team_tasks(
    status: Optional[TeamTaskStatus] = Query(None, description="按状态过滤"),
    team_id: Optional[str] = Query(None, description="按团队过滤"),
    page_size: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    orchestrator: TeamOrchestrator = Depends(_get_orchestrator),
):
    tasks, total = orchestrator.list_tasks(
        status=status,
        team_id=team_id,
        page_size=page_size,
        offset=offset,
    )
    return TeamTaskListResponse(
        items=tasks,
        total=total,
        page_size=page_size,
        offset=offset,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=TeamTask,
    summary="获取团队任务详情",
)
def get_team_task(
    task_id: str,
    orchestrator: TeamOrchestrator = Depends(_get_orchestrator),
):
    task = orchestrator.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@router.patch(
    "/tasks/{task_id}",
    response_model=TeamTask,
    summary="更新团队任务元信息",
)
def update_team_task(
    task_id: str,
    req: TeamTaskUpdate,
    orchestrator: TeamOrchestrator = Depends(_get_orchestrator),
):
    updated = orchestrator.update_task(task_id, req)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return updated


@router.post(
    "/tasks/{task_id}/next",
    response_model=TeamOrchestrateResponse,
    summary="推进任务到下一步（自动编排）",
)
def next_step(
    task_id: str,
    orchestrator: TeamOrchestrator = Depends(_get_orchestrator),
):
    req = TeamOrchestrateRequest(task_id=task_id, action="next_step")
    return orchestrator.orchestrate(req)


@router.post(
    "/tasks/{task_id}/assign",
    response_model=TeamOrchestrateResponse,
    summary="手动分配任务给指定角色",
)
def assign_task(
    task_id: str,
    role: TeamRole,
    agent: Optional[str] = None,
    message: Optional[str] = None,
    orchestrator: TeamOrchestrator = Depends(_get_orchestrator),
):
    req = TeamOrchestrateRequest(
        task_id=task_id,
        action="assign",
        target_role=role,
        target_agent=agent,
        input_message=message or "",
    )
    return orchestrator.orchestrate(req)


@router.post(
    "/tasks/{task_id}/execute",
    response_model=TeamOrchestrateResponse,
    summary="执行当前分配角色的任务步骤",
)
def execute_task(
    task_id: str,
    orchestrator: TeamOrchestrator = Depends(_get_orchestrator),
):
    req = TeamOrchestrateRequest(task_id=task_id, action="execute")
    return orchestrator.orchestrate(req)


@router.post(
    "/tasks/{task_id}/submit-review",
    response_model=TeamOrchestrateResponse,
    summary="提交任务产物进入评审",
)
def submit_review(
    task_id: str,
    orchestrator: TeamOrchestrator = Depends(_get_orchestrator),
):
    req = TeamOrchestrateRequest(task_id=task_id, action="submit_review")
    return orchestrator.orchestrate(req)


@router.post(
    "/tasks/{task_id}/review",
    response_model=TeamOrchestrateResponse,
    summary="对任务产出做评审",
)
def review_task(
    task_id: str,
    verdict: str,
    orchestrator: TeamOrchestrator = Depends(_get_orchestrator),
):
    req = TeamOrchestrateRequest(
        task_id=task_id,
        action="review",
        context_override={"verdict": verdict},
    )
    return orchestrator.orchestrate(req)


@router.post(
    "/tasks/{task_id}/unblock",
    response_model=TeamOrchestrateResponse,
    summary="解除阻塞状态",
)
def unblock_task(
    task_id: str,
    orchestrator: TeamOrchestrator = Depends(_get_orchestrator),
):
    req = TeamOrchestrateRequest(task_id=task_id, action="unblock")
    return orchestrator.orchestrate(req)


@router.post(
    "/tasks/{task_id}/orchestrate",
    response_model=TeamOrchestrateResponse,
    summary="通用编排推进（高级用法）",
)
def orchestrate(
    req: TeamOrchestrateRequest,
    orchestrator: TeamOrchestrator = Depends(_get_orchestrator),
):
    return orchestrator.orchestrate(req)
