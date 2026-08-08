"""API 层 - 请求/响应 Schema（Pydantic 强类型）。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    tenant_id: int = Field(1, description="租户 ID（P1 演示默认 1）")
    agent_id: int | None = Field(None, description="Agent 配置 ID")
    requirement: str = Field(..., description="需求描述", min_length=1)
    model: str = Field("deepseek-chat", description="模型偏好")


class GenerateResponse(BaseModel):
    success: bool
    trace_id: str | None = None
    requirement: str | None = None
    cases: list[dict[str, Any]] = []
    final_state: str | None = None
    paused: bool = False
    pause_reason: str | None = None
    error: str | None = None


class RagRequest(BaseModel):
    tenant_id: int = Field(1, description="租户 ID")
    agent_id: int | None = None
    question: str = Field(..., min_length=1)
    context: str = Field(default="", description="知识库上下文（P2 演示内联）")
    model: str = Field("deepseek-chat")


class RagResponse(BaseModel):
    success: bool
    question: str | None = None
    answer: str | None = None
    retrieved: list[str] = []
    trace_id: str | None = None
    error: str | None = None


class EvalRequest(BaseModel):
    tenant_id: int = 1
    task: str = Field(..., min_length=1, description="原始任务描述")
    output: str = Field(..., min_length=1, description="待评测产出")
    model: str = Field("deepseek-chat")


class EvalResponse(BaseModel):
    coverage: int = 0
    clarity: int = 0
    executability: int = 0
    score: float = 0.0
    summary: str = ""
