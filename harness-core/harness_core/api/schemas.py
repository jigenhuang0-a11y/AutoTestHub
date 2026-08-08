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
    error: str | None = None
