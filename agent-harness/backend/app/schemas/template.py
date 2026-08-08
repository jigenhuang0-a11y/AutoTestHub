"""
Phase 1.2：模板 API 的 Pydantic 请求/响应模型
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum


class TemplateStatusEnum(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


# ---- 步骤模型 ----

class WorkflowStepSchema(BaseModel):
    """单个步骤（API 输入/输出）"""
    order: int = Field(..., description="执行顺序")
    agent: str = Field(..., description="Agent 名称", examples=["generator", "execution"])
    prompt_template: str = Field(..., description="Prompt 模板，支持 {placeholder} 占位符")
    params_schema: dict = Field(default_factory=dict, description="参数 JSON Schema")
    parallel_group: Optional[str] = Field(None, description="并行组名，同组并行执行")
    timeout_seconds: int = Field(300, description="超时秒数")
    retry: int = Field(1, description="失败重试次数")
    depends_on: list[int] = Field(default_factory=list, description="依赖的前置步骤 order 列表")


# ---- 请求模型 ----

class TemplateCreateRequest(BaseModel):
    """创建模板请求"""
    model_config = {
        "protected_namespaces": (),
        "json_schema_extra": {
            "example": {
                "name": "安全测试流水线",
                "model_preference": "deepseek-chat",
                "steps": [
                    {
                        "order": 0,
                        "agent": "generator",
                        "prompt_template": "为 {module} 生成 {case_count} 条安全测试用例",
                        "params_schema": {
                            "module": {"type": "string", "required": True},
                            "case_count": {"type": "integer", "default": 10}
                        },
                        "timeout_seconds": 300,
                        "retry": 1,
                    }
                ],
                "metadata": {"description": "安全专项测试模板"},
            }
        }
    }

    name: str = Field(..., description="模板名称", examples=["安全测试流水线"])
    model_preference: str = Field("deepseek-chat", description="偏好模型")
    steps: list[WorkflowStepSchema] = Field(..., description="步骤列表")
    metadata: dict = Field(default_factory=dict, description="扩展元数据")


class TemplateUpdateRequest(BaseModel):
    """更新模板请求（自动版本+1）"""
    model_config = {"protected_namespaces": ()}

    name: Optional[str] = Field(None, description="模板名称")
    model_preference: Optional[str] = Field(None, description="偏好模型")
    steps: Optional[list[WorkflowStepSchema]] = Field(None, description="步骤列表")
    metadata: Optional[dict] = Field(None, description="扩展元数据")


# ---- 响应模型 ----

class TemplateResponse(BaseModel):
    """模板响应"""
    model_config = {
        "protected_namespaces": (),
        "json_schema_extra": {
            "example": {
                "template_id": "my_sec_pipeline_v1",
                "team_id": "team_alpha",
                "name": "安全测试流水线",
                "version": 1,
                "status": "draft",
                "model_preference": "deepseek-chat",
                "steps": [{"order": 0, "agent": "generator", "prompt_template": "...", "params_schema": {}}],
                "metadata": {},
                "created_at": 1753459200.0,
                "updated_at": 1753459200.0,
            }
        }
    }

    template_id: str
    team_id: str
    name: str
    version: int
    status: TemplateStatusEnum
    model_preference: str
    steps: list[WorkflowStepSchema]
    metadata: dict
    created_at: float
    updated_at: float


class TemplateListItem(BaseModel):
    """模板列表项（不含完整 steps）"""
    model_config = {"protected_namespaces": ()}

    template_id: str
    name: str
    version: int
    status: TemplateStatusEnum
    model_preference: str
    step_count: int
    created_at: float
    updated_at: float


class TemplateListResponse(BaseModel):
    """模板列表响应"""
    team_id: str
    templates: list[TemplateListItem]
    count: int


class TemplatePublishResponse(BaseModel):
    """发布响应"""
    template_id: str
    team_id: str
    version: int
    status: TemplateStatusEnum
    message: str
