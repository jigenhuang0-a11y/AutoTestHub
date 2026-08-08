"""SQLModel 基础模型：中台所有结构化数据的统一定义。

MySQL 存储。P0 只定义骨架表，P1 起逐步补全关系与索引。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class AgentStatus(str, Enum):
    active = "active"
    paused = "paused"
    archived = "archived"


class Tenant(SQLModel, table=True):
    """租户：多租户隔离的一级命名空间（team_id/user_id）。"""
    __tablename__ = "tenants"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=128, unique=True, index=True)
    api_key: str = Field(max_length=64, unique=True, index=True)
    token_quota: int = Field(default=1_000_000)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentConfig(SQLModel, table=True):
    """Agent 配置：每个业务插件实例的元数据与配额。"""
    __tablename__ = "agent_configs"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=128)
    plugin_key: str = Field(max_length=64, index=True)  # 对应 harness_plugins 注册 key
    model_preference: str = Field(default="deepseek-chat")
    status: AgentStatus = Field(default=AgentStatus.active)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CallLog(SQLModel, table=True):
    """调用埋点：全量 LLM / 工具调用记录，供评测与审计。"""
    __tablename__ = "call_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    agent_id: Optional[int] = Field(default=None, foreign_key="agent_configs.id")
    kind: str = Field(max_length=32)  # llm / tool / sandbox
    model: Optional[str] = Field(default=None)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    status: str = Field(default="ok", max_length=16)
    trace_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ToolRegistration(SQLModel, table=True):
    """工具注册中心：所有可调用的工具原语。"""
    __tablename__ = "tool_registrations"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=128)
    description: str = Field(default="")
    sandbox_required: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
