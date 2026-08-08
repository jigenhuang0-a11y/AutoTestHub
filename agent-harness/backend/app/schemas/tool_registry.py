"""
工具注册 Schema — 底座接收 Django 推送的工具注册
"""
from typing import Optional
from pydantic import BaseModel, Field


class ToolRegisterItem(BaseModel):
    """单个工具注册项"""
    name: str = Field(..., description="工具名（kebab-case）")
    description: str = Field(..., description="工具描述")
    input_schema: dict = Field(default_factory=dict, description="JSON Schema 参数定义")
    category: str = Field(default="general", description="工具分类")
    owner_team_id: Optional[str] = Field(default=None, description="所属团队（None=全局）")


class ToolBatchRegister(BaseModel):
    """批量工具注册请求"""
    tools: list[ToolRegisterItem] = Field(..., description="工具列表")
    django_url: Optional[str] = Field(default=None, description="Django 服务地址")
    auth_token: Optional[str] = Field(default=None, description="认证 Token")


class ToolRegisterResponse(BaseModel):
    """工具注册响应"""
    registered: int = Field(default=0, description="成功注册数")
    updated: int = Field(default=0, description="更新数")
    failed: int = Field(default=0, description="失败数")
    errors: list[str] = Field(default_factory=list, description="错误信息")


class ToolRefreshRequest(BaseModel):
    """工具刷新请求（Django 变更后触发）"""
    force: bool = Field(default=True, description="是否强制立即刷新")
    team_id: Optional[str] = Field(default=None, description="目标团队")


class ToolStatusResponse(BaseModel):
    """工具状态响应"""
    total_tools: int = Field(default=0, description="已缓存工具数")
    agent_mappings: int = Field(default=0, description="Agent 映射数")
    last_refresh: float = Field(default=0, description="上次刷新时间戳")
    is_stale: bool = Field(default=True, description="是否过期")
    discovery_healthy: bool = Field(default=False, description="发现器是否正常")
