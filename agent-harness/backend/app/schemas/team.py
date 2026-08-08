"""
多 Agent 团队编排 Schema

定义团队任务生命周期、角色、交接消息和评审门控的数据模型。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================
# 枚举
# ============================================================

class TeamTaskStatus(str, Enum):
    """团队任务生命周期状态"""
    INBOX = "inbox"                 # 新任务进入，待分类
    ASSIGNED = "assigned"           # 已分配给执行角色
    IN_PROGRESS = "in_progress"     # 执行中
    REVIEW = "review"               # 等待评审
    DONE = "done"                   # 已完成
    FAILED = "failed"               # 执行失败
    BLOCKED = "blocked"             # 被阻塞，需要人工介入


class TeamRole(str, Enum):
    """预定义团队角色"""
    ORCHESTRATOR = "orchestrator"   # 任务路由与策略制定
    PLANNER = "planner"             # 拆解方案
    BUILDER = "builder"             # 生成代码/用例/数据
    REVIEWER = "reviewer"           # 质量评审
    OPS = "ops"                     # 运行/部署/验证


class ReviewVerdict(str, Enum):
    """评审结论"""
    ACCEPT = "accept"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


class HandoffIntent(str, Enum):
    """交接意图"""
    DELEGATE = "delegate"             # 委派任务
    ESCALATE = "escalate"           # 升级问题
    HAND_BACK = "hand_back"         # 打回重做
    CLOSE = "close"                 # 任务完成交接


# ============================================================
# 基础模型
# ============================================================

class Artifact(BaseModel):
    """任务产物（文件、用例、报告等）"""
    name: str
    artifact_type: str = Field(default="", description="产物类型：test_case / data / code / report / log")
    content: str = Field(default="", description="文本内容或 JSON 字符串")
    metadata: dict[str, Any] = Field(default_factory=dict)


class HandoffMessage(BaseModel):
    """
    交接消息 — 必须包含 5 要素：
    1. from / to: 交接双方
    2. context: 背景与目标
    3. deliverables: 已完成交付物
    4. blockers: 阻塞/风险
    5. intent: 交接意图
    """
    handoff_id: str = Field(default="", description="交接唯一 ID")
    task_id: str
    from_role: TeamRole
    to_role: TeamRole
    from_agent: str = Field(default="", description="具体 Agent 实例名")
    to_agent: str = Field(default="", description="具体 Agent 实例名")
    intent: HandoffIntent = Field(default=HandoffIntent.DELEGATE)
    context: str = Field(default="", description="背景与目标")
    deliverables: list[Artifact] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    notes: str = Field(default="")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @field_validator("deliverables", mode="before")
    @classmethod
    def _ensure_list(cls, v: Any) -> list:
        if v is None:
            return []
        return v


class ReviewRequest(BaseModel):
    """评审请求"""
    review_id: str = Field(default="")
    task_id: str
    reviewer_role: TeamRole = Field(default=TeamRole.REVIEWER)
    reviewer_agent: str = Field(default="")
    builder_agent: str = Field(default="")
    artifacts: list[Artifact] = Field(default_factory=list)
    criteria: list[str] = Field(default_factory=list, description="评审标准")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ReviewResult(BaseModel):
    """评审结果"""
    review_id: str
    task_id: str
    verdict: ReviewVerdict
    reviewer_agent: str = Field(default="")
    score: Optional[int] = Field(default=None, ge=0, le=100, description="0-100 质量分")
    comments: list[str] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ============================================================
# 任务模型
# ============================================================

class TeamTaskCreate(BaseModel):
    """创建团队任务请求"""
    title: str = Field(..., min_length=1)
    description: str = Field(default="")
    team_id: str = Field(default="default")
    user_id: str = Field(default="")
    required_roles: list[TeamRole] = Field(default_factory=lambda: [TeamRole.ORCHESTRATOR, TeamRole.BUILDER])
    tags: list[str] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)
    parent_task_id: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None, description="指定 LLM 模型")
    context: dict[str, Any] = Field(default_factory=dict, description="业务上下文")


class TeamTaskUpdate(BaseModel):
    """更新团队任务请求"""
    status: Optional[TeamTaskStatus] = None
    assigned_to: Optional[TeamRole] = None
    assigned_agent: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    context: Optional[dict[str, Any]] = None


class TeamTask(BaseModel):
    """团队任务完整记录"""
    task_id: str
    title: str
    description: str = ""
    status: TeamTaskStatus = Field(default=TeamTaskStatus.INBOX)
    team_id: str = "default"
    user_id: str = ""
    assigned_to: Optional[TeamRole] = None
    assigned_agent: Optional[str] = None
    required_roles: list[TeamRole] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    priority: int = 3
    parent_task_id: Optional[str] = None
    model: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[Artifact] = Field(default_factory=list)
    handoffs: list[HandoffMessage] = Field(default_factory=list)
    reviews: list[ReviewResult] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


# ============================================================
# 编排请求/响应
# ============================================================

class TeamOrchestrateRequest(BaseModel):
    """对团队任务执行一次编排推进"""
    task_id: str
    action: str = Field(..., description="next_step / assign / execute / review / unblock")
    target_role: Optional[TeamRole] = None
    target_agent: Optional[str] = None
    input_message: Optional[str] = None
    artifacts: list[Artifact] = Field(default_factory=list)
    context_override: dict[str, Any] = Field(default_factory=dict)


class TeamOrchestrateResponse(BaseModel):
    """编排推进结果"""
    task_id: str
    status: TeamTaskStatus
    assigned_to: Optional[TeamRole] = None
    assigned_agent: Optional[str] = None
    handoff: Optional[HandoffMessage] = None
    review: Optional[ReviewResult] = None
    artifacts: list[Artifact] = Field(default_factory=list)
    message: str = ""


class TeamTaskListResponse(BaseModel):
    """任务列表响应"""
    items: list[TeamTask]
    total: int
    page_size: int
    offset: int
