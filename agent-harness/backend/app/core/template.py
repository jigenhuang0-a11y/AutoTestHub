"""
Phase 1.2：工作流模板数据模型

定义：
- WorkflowStep：单个执行步骤
- WorkflowTemplate：团队级工作流模板
- DEFAULT_TEMPLATES：平台预设模板
"""

import json
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class TemplateStatus(str, Enum):
    """模板状态"""
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


@dataclass
class WorkflowStep:
    """工作流执行步骤"""
    order: int
    agent: str                      # "generator" | "data_factory" | "execution" | "evaluator"
    prompt_template: str            # "为 {module} 生成 {case_count} 条用例"
    params_schema: dict = field(default_factory=dict)   # JSON Schema
    parallel_group: Optional[str] = None
    timeout_seconds: int = 300
    retry: int = 1
    depends_on: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "order": self.order,
            "agent": self.agent,
            "prompt_template": self.prompt_template,
            "params_schema": self.params_schema,
            "parallel_group": self.parallel_group,
            "timeout_seconds": self.timeout_seconds,
            "retry": self.retry,
            "depends_on": self.depends_on,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowStep":
        return cls(
            order=data.get("order", 0),
            agent=data.get("agent", ""),
            prompt_template=data.get("prompt_template", ""),
            params_schema=data.get("params_schema", {}),
            parallel_group=data.get("parallel_group"),
            timeout_seconds=data.get("timeout_seconds", 300),
            retry=data.get("retry", 1),
            depends_on=data.get("depends_on", []),
        )


@dataclass
class WorkflowTemplate:
    """工作流模板"""
    template_id: str
    team_id: str
    name: str
    version: int = 1
    status: TemplateStatus = TemplateStatus.DRAFT
    model_preference: str = "deepseek-chat"
    steps: list[WorkflowStep] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.updated_at == 0.0:
            self.updated_at = self.created_at

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "team_id": self.team_id,
            "name": self.name,
            "version": self.version,
            "status": self.status.value,
            "model_preference": self.model_preference,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowTemplate":
        status = data.get("status", "draft")
        if isinstance(status, str):
            status = TemplateStatus(status)
        steps_data = data.get("steps", [])
        steps = [WorkflowStep.from_dict(s) for s in steps_data]
        return cls(
            template_id=data.get("template_id", ""),
            team_id=data.get("team_id", ""),
            name=data.get("name", ""),
            version=data.get("version", 1),
            status=status,
            model_preference=data.get("model_preference", "deepseek-chat"),
            steps=steps,
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
        )

    def bump_version(self):
        """版本号 +1，更新时间戳"""
        self.version += 1
        self.updated_at = time.time()

    def publish(self):
        """发布模板"""
        self.status = TemplateStatus.PUBLISHED
        self.updated_at = time.time()


# ============================================================
# 平台预设模板（team_id="default"）
# ============================================================

DEFAULT_TEMPLATES: dict[str, WorkflowTemplate] = {
    "standard_pipeline_v1": WorkflowTemplate(
        template_id="standard_pipeline_v1",
        team_id="default",
        name="标准测试生成流水线",
        version=1,
        status=TemplateStatus.PUBLISHED,
        model_preference="deepseek-chat",
        steps=[
            WorkflowStep(
                order=0, agent="generator",
                prompt_template="{user_request}",
                params_schema={
                    "requirement": {"type": "string", "required": True},
                    "case_count": {"type": "integer", "default": 10},
                },
                parallel_group="A",
            ),
            WorkflowStep(
                order=1, agent="data_factory",
                prompt_template="为上述用例生成测试数据",
                params_schema={
                    "business_domain": {"type": "string", "required": True},
                    "record_count": {"type": "integer", "default": 20},
                },
                parallel_group="A",
            ),
            WorkflowStep(
                order=2, agent="execution",
                prompt_template="执行生成的测试用例",
                params_schema={"test_case_ids": {"type": "array", "required": True}},
            ),
            WorkflowStep(
                order=3, agent="evaluator",
                prompt_template="评估执行结果",
                params_schema={"execution_id": {"type": "integer", "required": True}},
            ),
        ],
    ),

    "quick_validate_v1": WorkflowTemplate(
        template_id="quick_validate_v1",
        team_id="default",
        name="快速验证流水线",
        version=1,
        status=TemplateStatus.PUBLISHED,
        model_preference="qwen-turbo",
        steps=[
            WorkflowStep(
                order=0, agent="generator",
                prompt_template="{user_request}",
                params_schema={
                    "requirement": {"type": "string", "required": True},
                    "case_count": {"type": "integer", "default": 5},
                },
            ),
            WorkflowStep(
                order=1, agent="execution",
                prompt_template="执行生成的测试用例",
                params_schema={"test_case_ids": {"type": "array", "required": True}},
            ),
        ],
    ),

    "eval_first_v1": WorkflowTemplate(
        template_id="eval_first_v1",
        team_id="default",
        name="评测优先流水线",
        version=1,
        status=TemplateStatus.PUBLISHED,
        model_preference="deepseek-chat",
        steps=[
            WorkflowStep(
                order=0, agent="data_factory",
                prompt_template="为 {module} 生成测试数据",
                params_schema={
                    "business_domain": {"type": "string", "required": True},
                    "record_count": {"type": "integer", "default": 50},
                },
            ),
            WorkflowStep(
                order=1, agent="generator",
                prompt_template="{user_request}",
                params_schema={
                    "requirement": {"type": "string", "required": True},
                    "case_count": {"type": "integer", "default": 10},
                },
            ),
            WorkflowStep(
                order=2, agent="execution",
                prompt_template="执行生成的测试用例",
                params_schema={"test_case_ids": {"type": "array", "required": True}},
            ),
            WorkflowStep(
                order=3, agent="evaluator",
                prompt_template="评估执行结果并输出报告",
                params_schema={"execution_id": {"type": "integer", "required": True}},
            ),
        ],
    ),
}


def dumps(template: WorkflowTemplate) -> str:
    """序列化为 JSON 字符串"""
    return json.dumps(template.to_dict(), ensure_ascii=False)


def loads(data: str) -> WorkflowTemplate:
    """从 JSON 字符串反序列化"""
    return WorkflowTemplate.from_dict(json.loads(data))
