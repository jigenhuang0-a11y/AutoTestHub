"""
Phase 1.2：模板管理 API 端点

提供团队级工作流模板的 CRUD 操作：
- GET  /{team_id}                       列出团队所有模板
- GET  /{team_id}/{template_id}         获取单个模板
- POST /{team_id}                       创建新模板
- PUT  /{team_id}/{template_id}         更新模板（自动版本+1）
- DELETE /{team_id}/{template_id}       删除模板
- POST /{team_id}/{template_id}/publish 发布模板
"""

import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Path

from app.api.v1.endpoints.auth import require_non_viewer

from app.core.template import WorkflowTemplate, WorkflowStep, TemplateStatus
from app.core.template_store import get_template_store
from app.schemas.template import (
    TemplateCreateRequest,
    TemplateUpdateRequest,
    TemplateResponse,
    TemplateListItem,
    TemplateListResponse,
    TemplatePublishResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _template_to_response(tmpl: WorkflowTemplate) -> TemplateResponse:
    """将内部模型转为 API 响应"""
    from app.schemas.template import WorkflowStepSchema
    return TemplateResponse(
        template_id=tmpl.template_id,
        team_id=tmpl.team_id,
        name=tmpl.name,
        version=tmpl.version,
        status=TemplateStatus(tmpl.status.value),
        model_preference=tmpl.model_preference,
        steps=[
            WorkflowStepSchema(
                order=s.order,
                agent=s.agent,
                prompt_template=s.prompt_template,
                params_schema=s.params_schema,
                parallel_group=s.parallel_group,
                timeout_seconds=s.timeout_seconds,
                retry=s.retry,
                depends_on=s.depends_on,
            )
            for s in tmpl.steps
        ],
        metadata=tmpl.metadata,
        created_at=tmpl.created_at,
        updated_at=tmpl.updated_at,
    )


@router.get("/{team_id}", response_model=TemplateListResponse)
async def list_templates(team_id: str = Path(..., description="团队 ID")):
    """列出团队所有模板"""
    store = get_template_store()
    templates = await store.list(team_id)

    items = [
        TemplateListItem(
            template_id=t.template_id,
            name=t.name,
            version=t.version,
            status=TemplateStatus(t.status.value),
            model_preference=t.model_preference,
            step_count=len(t.steps),
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in templates
    ]

    return TemplateListResponse(team_id=team_id, templates=items, count=len(items))


@router.get("/{team_id}/{template_id}", response_model=TemplateResponse)
async def get_template(
    team_id: str = Path(..., description="团队 ID"),
    template_id: str = Path(..., description="模板 ID"),
):
    """获取单个模板详情"""
    store = get_template_store()
    tmpl = await store.get(team_id, template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"模板不存在: {team_id}/{template_id}")
    return _template_to_response(tmpl)


@router.post("/{team_id}", response_model=TemplateResponse, status_code=201)
async def create_template(
    req: TemplateCreateRequest,
    team_id: str = Path(..., description="团队 ID"),
    user: dict = Depends(require_non_viewer),
):
    """创建新模板"""
    store = get_template_store()

    # 生成 template_id：name 拼音首字母 + 随机后缀
    name_slug = "".join(c for c in req.name if c.isalnum() or c in ("_", "-")).lower()[:20]
    template_id = f"{name_slug}_{uuid.uuid4().hex[:6]}"

    now = time.time()
    steps = [
        WorkflowStep(
            order=s.order,
            agent=s.agent,
            prompt_template=s.prompt_template,
            params_schema=s.params_schema,
            parallel_group=s.parallel_group,
            timeout_seconds=s.timeout_seconds,
            retry=s.retry,
            depends_on=s.depends_on,
        )
        for s in req.steps
    ]

    tmpl = WorkflowTemplate(
        template_id=template_id,
        team_id=team_id,
        name=req.name,
        version=1,
        status=TemplateStatus.DRAFT,
        model_preference=req.model_preference,
        steps=steps,
        metadata=req.metadata,
        created_at=now,
        updated_at=now,
    )

    await store.save(tmpl)
    logger.info(f"[Templates] 创建模板: {team_id}/{template_id} '{req.name}'")
    return _template_to_response(tmpl)


@router.put("/{team_id}/{template_id}", response_model=TemplateResponse)
async def update_template(
    req: TemplateUpdateRequest,
    team_id: str = Path(..., description="团队 ID"),
    template_id: str = Path(..., description="模板 ID"),
    user: dict = Depends(require_non_viewer),
):
    """更新模板（自动版本+1）"""
    store = get_template_store()
    tmpl = await store.get(team_id, template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"模板不存在: {team_id}/{template_id}")

    tmpl.bump_version()

    if req.name is not None:
        tmpl.name = req.name
    if req.model_preference is not None:
        tmpl.model_preference = req.model_preference
    if req.steps is not None:
        tmpl.steps = [
            WorkflowStep(
                order=s.order,
                agent=s.agent,
                prompt_template=s.prompt_template,
                params_schema=s.params_schema,
                parallel_group=s.parallel_group,
                timeout_seconds=s.timeout_seconds,
                retry=s.retry,
                depends_on=s.depends_on,
            )
            for s in req.steps
        ]
    if req.metadata is not None:
        tmpl.metadata = req.metadata

    tmpl.status = TemplateStatus.DRAFT  # 更新后变为草稿
    tmpl.updated_at = time.time()

    await store.save(tmpl)
    logger.info(f"[Templates] 更新模板: {team_id}/{template_id} → v{tmpl.version}")
    return _template_to_response(tmpl)


@router.delete("/{team_id}/{template_id}")
async def delete_template(
    team_id: str = Path(..., description="团队 ID"),
    template_id: str = Path(..., description="模板 ID"),
    user: dict = Depends(require_non_viewer),
):
    """删除模板"""
    store = get_template_store()
    deleted = await store.delete(team_id, template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"模板不存在: {team_id}/{template_id}")
    logger.info(f"[Templates] 删除模板: {team_id}/{template_id}")
    return {"status": "ok", "message": f"模板 {template_id} 已删除"}


@router.post("/{team_id}/{template_id}/publish", response_model=TemplatePublishResponse)
async def publish_template(
    team_id: str = Path(..., description="团队 ID"),
    template_id: str = Path(..., description="模板 ID"),
    user: dict = Depends(require_non_viewer),
):
    """发布模板（状态 draft → published）"""
    store = get_template_store()
    tmpl = await store.get(team_id, template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"模板不存在: {team_id}/{template_id}")

    tmpl.publish()
    await store.save(tmpl)

    logger.info(f"[Templates] 发布模板: {team_id}/{template_id} v{tmpl.version}")
    return TemplatePublishResponse(
        template_id=tmpl.template_id,
        team_id=tmpl.team_id,
        version=tmpl.version,
        status=TemplateStatus(tmpl.status.value),
        message=f"模板 {template_id} v{tmpl.version} 已发布",
    )
