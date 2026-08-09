"""
测试环境管理接口（Phase 2.6）

提供多套测试环境的 CRUD：
  - GET    /api/v1/agent/environments      列表
  - POST   /api/v1/agent/environments      创建
  - PUT    /api/v1/agent/environments/{id} 更新
  - DELETE /api/v1/agent/environments/{id} 删除

环境数据持久化在 environments 表，供工作流注入 base_url 等配置。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.v1.endpoints.auth import require_admin
from app.core.task_store import get_task_store

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_admin)])


class EnvCreate(BaseModel):
    name: str
    env_type: str = "test"          # test / staging / prod
    base_url: str = ""
    description: str = ""
    owner: str = ""
    status: str = "active"


class EnvUpdate(BaseModel):
    name: str = None
    env_type: str = None
    base_url: str = None
    description: str = None
    owner: str = None
    status: str = None


@router.get("/")
async def list_environments(env_type: str = ""):
    """获取测试环境列表"""
    store = get_task_store()
    items = [e.to_dict() for e in store.list_environments(env_type)]
    return {"items": items, "total": len(items)}


@router.post("/", status_code=201)
async def create_environment(payload: EnvCreate):
    """创建测试环境"""
    store = get_task_store()
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="环境名称不能为空")
    if payload.env_type not in ("test", "staging", "prod"):
        raise HTTPException(status_code=400, detail="env_type 必须是 test/staging/prod")
    rec = store.create_environment(
        name=payload.name.strip(),
        env_type=payload.env_type,
        base_url=payload.base_url,
        description=payload.description,
        owner=payload.owner,
        status=payload.status,
    )
    return rec.to_dict()


@router.put("/{env_id}/")
async def update_environment(env_id: str, payload: EnvUpdate):
    """更新测试环境"""
    store = get_task_store()
    existing = store.get_environment(env_id)
    if not existing:
        raise HTTPException(status_code=404, detail="环境不存在")
    rec = store.update_environment(
        env_id,
        name=payload.name,
        env_type=payload.env_type,
        base_url=payload.base_url,
        description=payload.description,
        owner=payload.owner,
        status=payload.status,
    )
    return rec.to_dict()


@router.delete("/{env_id}/")
async def delete_environment(env_id: str):
    """删除测试环境"""
    store = get_task_store()
    ok = store.delete_environment(env_id)
    if not ok:
        raise HTTPException(status_code=404, detail="环境不存在")
    return {"id": env_id, "status": "deleted"}
