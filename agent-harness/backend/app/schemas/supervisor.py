from pydantic import BaseModel, Field
from typing import Optional


class SupervisorStreamRequest(BaseModel):
    """Supervisor-Worker 多代理编排（流式）请求"""
    user_request: str = Field(..., description="用户原始需求（自然语言）")
    task_id: Optional[str] = Field(None, description="任务 ID，为空则自动生成")
    user_id: Optional[int] = Field(None, description="用户 ID")
    team_id: Optional[str] = Field("default", description="团队 ID，用于匹配偏好/模板")
    template_id: Optional[str] = Field(None, description="指定模板 ID；为空则用团队默认")
    model: Optional[str] = Field(None, description="强制指定编排使用的模型；为空用团队偏好/全局路由")
    auth_token: Optional[str] = Field(None, description="Django 认证 Token")


class SupervisorInvokeRequest(SupervisorStreamRequest):
    """Supervisor-Worker 多代理编排（同步）请求"""
    pass
