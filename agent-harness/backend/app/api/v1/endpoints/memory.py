"""
记忆系统 REST API — 暴露底座记忆能力给 Django 等业务层

所有操作通过 team_id 隔离，支持：
- POST /api/v1/memory/remember    → 写入记忆
- POST /api/v1/memory/recall      → 检索记忆
- POST /api/v1/memory/context     → 获取完整记忆上下文
- POST /api/v1/memory/task/start  → 开始任务
- POST /api/v1/memory/task/close  → 结束任务
- GET  /api/v1/memory/health      → 健康检查
"""

import logging
from typing import Optional
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.memory import MemoryManager, MemoryType, MemoryImportance

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================
# 请求/响应模型
# ============================================================


class RememberRequest(BaseModel):
    team_id: str = "default"
    user_id: Optional[int] = None
    content: str
    memory_type: str = "fact"        # fact/decision/pattern/lesson
    importance: str = "medium"       # low/medium/high/critical
    metadata: Optional[dict] = None


class RecallRequest(BaseModel):
    team_id: str = "default"
    user_id: Optional[int] = None
    query: str
    limit: int = 5


class ContextRequest(BaseModel):
    team_id: str = "default"
    user_id: Optional[int] = None
    query: Optional[str] = None


class TaskRequest(BaseModel):
    team_id: str = "default"
    user_id: Optional[int] = None
    task_id: str


class RememberResponse(BaseModel):
    memory_id: str
    team_id: str


class RecallResponse(BaseModel):
    context: str
    team_id: str


class ContextResponse(BaseModel):
    context: str
    team_id: str


class TaskResponse(BaseModel):
    task_id: str
    status: str


class HealthResponse(BaseModel):
    status: str
    details: dict


# ============================================================
# 工厂：为每次请求创建独立 MemoryManager 实例
# ============================================================

# 注：当前为简化实现，每个请求创建新实例。
#     后续可接入 Redis 做进程间共享的短期记忆。


def _str_to_memory_type(s: str) -> MemoryType:
    mapping = {
        "fact": MemoryType.FACT,
        "decision": MemoryType.DECISION,
        "pattern": MemoryType.PATTERN,
        "lesson": MemoryType.LESSON,
    }
    return mapping.get(s, MemoryType.FACT)


def _str_to_importance(s: str) -> MemoryImportance:
    mapping = {
        "low": MemoryImportance.LOW,
        "medium": MemoryImportance.MEDIUM,
        "high": MemoryImportance.HIGH,
        "critical": MemoryImportance.CRITICAL,
    }
    return mapping.get(s, MemoryImportance.MEDIUM)


# ============================================================
# 端点
# ============================================================


@router.post("/remember", response_model=RememberResponse)
async def remember(request: RememberRequest):
    """写入一条记忆"""
    mm = MemoryManager(team_id=request.team_id, user_id=request.user_id)
    try:
        mem_id = mm.remember(
            content=request.content,
            memory_type=_str_to_memory_type(request.memory_type),
            importance=_str_to_importance(request.importance),
            metadata=request.metadata,
        )
        return RememberResponse(memory_id=mem_id, team_id=request.team_id)
    except Exception as e:
        logger.exception(f"[MemoryAPI] remember 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recall", response_model=RecallResponse)
async def recall(request: RecallRequest):
    """检索相关记忆"""
    mm = MemoryManager(team_id=request.team_id, user_id=request.user_id)
    try:
        context = mm.recall(query=request.query, limit=request.limit)
        return RecallResponse(context=context, team_id=request.team_id)
    except Exception as e:
        logger.exception(f"[MemoryAPI] recall 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/context", response_model=ContextResponse)
async def get_context(request: ContextRequest):
    """获取完整记忆上下文（用于注入 ReAct system prompt）"""
    mm = MemoryManager(team_id=request.team_id, user_id=request.user_id)
    try:
        context = mm.get_memory_context(query=request.query)
        return ContextResponse(context=context, team_id=request.team_id)
    except Exception as e:
        logger.exception(f"[MemoryAPI] context 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/task/start", response_model=TaskResponse)
async def start_task(request: TaskRequest):
    """开始新任务：创建新的工作记忆"""
    mm = MemoryManager(team_id=request.team_id, user_id=request.user_id)
    try:
        mm.start_task(request.task_id)
        return TaskResponse(task_id=request.task_id, status="started")
    except Exception as e:
        logger.exception(f"[MemoryAPI] start_task 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/task/close", response_model=TaskResponse)
async def close_task(request: TaskRequest):
    """结束任务：清理工作记忆"""
    mm = MemoryManager(team_id=request.team_id, user_id=request.user_id)
    try:
        mm.close_task()
        return TaskResponse(task_id=request.task_id, status="closed")
    except Exception as e:
        logger.exception(f"[MemoryAPI] close_task 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health():
    """记忆系统健康检查"""
    mm = MemoryManager()
    return HealthResponse(status="ok", details=mm.health())
