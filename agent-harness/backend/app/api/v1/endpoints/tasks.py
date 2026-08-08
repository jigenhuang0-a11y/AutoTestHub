"""
Agent 任务监控接口 — Phase 2.1：真实持久化

用 TaskStore（SQLite）替代全部内存 mock 数据。
前端 API 兼容：Pydantic response_model 不变，字段名不变。
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.api.v1.endpoints.auth import require_non_viewer
from pydantic import BaseModel

from app.core.task_store import (
    get_task_store,
    TaskRecord,
    TraceStepRecord,
)

router = APIRouter()

# ============================================================
# Pydantic 响应模型（与前端约定一致，保持不变）
# ============================================================


class TaskItem(BaseModel):
    id: str
    task_type: str
    user_request: str
    status: str
    steps_count: int
    duration_ms: int
    created_at: str


class TaskTrace(BaseModel):
    id: str
    task_type: str
    user_request: str
    status: str
    created_at: str


class TraceStep(BaseModel):
    step: int
    phase: str
    title: str
    thinking: str
    action: str
    duration_ms: int
    status: str
    output: dict


class TraceDetail(BaseModel):
    id: str
    steps: list[TraceStep]


class TaskStats(BaseModel):
    summary: dict
    today_calls: int
    avg_duration_ms: int
    success_rate: int
    trend: list[dict]
    sandbox_usage: list[dict]


class TaskList(BaseModel):
    count: int
    results: list[TaskItem]


class PromptItem(BaseModel):
    id: int
    agent_name: str
    prompt_type: str
    prompt_subtype: str
    system_prompt: str
    user_prompt_template: str
    version: int
    is_active: bool


class PromptUpdate(BaseModel):
    system_prompt: str
    user_prompt_template: str


# ============================================================
# 工具函数
# ============================================================


def _task_to_item(t: TaskRecord) -> TaskItem:
    return TaskItem(
        id=t.id,
        task_type=t.task_type,
        user_request=t.user_request,
        status=t.status,
        steps_count=t.steps_count,
        duration_ms=t.duration_ms,
        created_at=t.created_at,
    )


def _task_to_trace(t: TaskRecord) -> TaskTrace:
    return TaskTrace(
        id=t.id,
        task_type=t.task_type,
        user_request=t.user_request,
        status=t.status,
        created_at=t.created_at,
    )


# ============================================================
# 任务统计（卡片 + 图表）
# ============================================================


@router.get("/stats/", response_model=TaskStats)
async def get_task_stats():
    """获取任务监控统计卡片和图表数据。"""
    store = get_task_store()
    stats = store.get_stats()
    return TaskStats(**stats)


# ============================================================
# 任务列表
# ============================================================


@router.get("/", response_model=TaskList)
async def list_tasks(
    status: Optional[str] = Query(None, description="按状态过滤"),
    page_size: int = Query(50, ge=1, le=100),
):
    """获取任务列表（按创建时间倒序）。"""
    store = get_task_store()
    records, total = store.list_tasks(status=status, page_size=page_size)
    items = [_task_to_item(r) for r in records]
    return TaskList(count=total, results=items)


@router.get("/latest/", response_model=TaskList)
async def latest_tasks(limit: int = Query(10, ge=1, le=100)):
    """获取最新任务列表（用于其他页面快速展示）。"""
    store = get_task_store()
    records = store.list_recent(limit=limit)
    items = [_task_to_item(r) for r in records]
    return TaskList(count=len(items), results=items)


# ============================================================
# 链路搜索 + 详情
# ============================================================


@router.get("/trace/", response_model=list[TaskTrace])
async def search_traces(
    q: Optional[str] = Query(None, description="搜索关键词"),
    status: Optional[str] = Query(None, description="按状态过滤"),
    page_size: int = Query(50, ge=1, le=100),
):
    """搜索任务链路（左侧任务列表）。"""
    store = get_task_store()
    records = store.search_tasks(q=q, status=status, page_size=page_size)
    return [_task_to_trace(r) for r in records]


@router.get("/trace/{task_id}/", response_model=TraceDetail)
async def get_task_trace(task_id: str):
    """获取单个任务的执行链路详情。"""
    store = get_task_store()
    step_records = store.get_trace_steps(task_id)

    # 如果没有任何 trace 记录，返回空列表（不再随机 mock）
    steps = []
    if step_records:
        for sr in step_records:
            steps.append(TraceStep(**sr.to_dict()))

    return TraceDetail(id=task_id, steps=steps)


# ============================================================
# 模型配置
# ============================================================


@router.get("/models/", response_model=dict)
async def list_models():
    """获取模型配置列表。"""
    store = get_task_store()
    models = [m.to_dict() for m in store.list_models()]
    return {"models": models}


# ============================================================
# Prompt 管理
# ============================================================


@router.get("/prompts/", response_model=dict)
async def list_prompts():
    """获取 Prompt 配置列表。"""
    store = get_task_store()
    prompts = [p.to_dict() for p in store.list_prompts()]
    return {"results": prompts}


@router.put("/prompts/{prompt_id}/", response_model=PromptItem)
async def update_prompt(
    prompt_id: int,
    payload: PromptUpdate = Body(...),
    user: dict = Depends(require_non_viewer),
):
    """更新 Prompt（版本号自动 +1，持久化到 SQLite）。"""
    store = get_task_store()
    updated = store.update_prompt(
        prompt_id=prompt_id,
        system_prompt=payload.system_prompt,
        user_prompt_template=payload.user_prompt_template,
    )
    if updated is None:
        # 不存在则自动创建
        from app.core.task_store import PromptRecord
        now = datetime.now(timezone.utc).isoformat()
        record = PromptRecord(
            id=prompt_id,
            agent_name="unknown",
            prompt_type="system",
            prompt_subtype="default",
            system_prompt=payload.system_prompt,
            user_prompt_template=payload.user_prompt_template,
            version=1,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        return PromptItem(**record.to_dict())

    return PromptItem(**updated.to_dict())
