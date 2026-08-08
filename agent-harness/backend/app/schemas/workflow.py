from pydantic import BaseModel, Field
from typing import Optional, Any


class WorkflowInvokeRequest(BaseModel):
    """同步工作流请求"""
    user_request: str = Field(..., description="用户原始需求")
    task_id: Optional[str] = Field(None, description="任务 ID，用于断点续跑；为空则自动生成")
    user_id: Optional[int] = Field(None, description="用户 ID")
    team_id: Optional[str] = Field("default", description="团队 ID，用于匹配工作流模板")
    template_id: Optional[str] = Field(None, description="指定模板 ID；为空则用团队默认模板")
    auth_token: Optional[str] = Field(None, description="Django 认证 Token")


class WorkflowStreamRequest(BaseModel):
    """流式工作流请求"""
    user_request: str = Field(..., description="用户原始需求")
    task_id: Optional[str] = Field(None, description="任务 ID，用于断点续跑；为空则自动生成")
    user_id: Optional[int] = Field(None, description="用户 ID")
    team_id: Optional[str] = Field("default", description="团队 ID，用于匹配工作流模板")
    template_id: Optional[str] = Field(None, description="指定模板 ID；为空则用团队默认模板")
    auth_token: Optional[str] = Field(None, description="Django 认证 Token")


class WorkflowResumeRequest(BaseModel):
    """专用断点续跑请求（可选覆盖原参数）"""
    user_request: Optional[str] = Field(None, description="可选，更新用户需求")
    user_id: Optional[int] = Field(None, description="可选，更新用户 ID")
    team_id: Optional[str] = Field(None, description="可选，更新团队 ID")
    template_id: Optional[str] = Field(None, description="可选，更新模板 ID")
    auth_token: Optional[str] = Field(None, description="可选，更新认证 Token")


class WorkflowInvokeResponse(BaseModel):
    """同步工作流响应"""
    task_id: str
    status: str
    plan: list
    results: list
    verification: dict


class CheckpointResponse(BaseModel):
    """Checkpoint 查询响应"""
    task_id: str
    exists: bool
    phase: Optional[str] = None
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    completed_steps: Optional[list[int]] = None
    retry_count: Optional[int] = None
    step_retry_counts: Optional[dict[int, int]] = None
    created_at: Optional[float] = None
    compatible: Optional[bool] = None


class ResumeCheckpointResponse(BaseModel):
    """断点续跑响应（非流式时）"""
    task_id: str
    resumed: bool
    phase: Optional[str] = None
    message: str = ""
    retry_count: Optional[int] = None
    completed_steps: Optional[list[int]] = None


class RetryStepResponse(BaseModel):
    """单步重试响应"""
    task_id: str
    step_index: int
    retried: bool
    status: Optional[str] = None
    message: Optional[str] = None
    result: Optional[Any] = None
    retry_count: Optional[int] = None
