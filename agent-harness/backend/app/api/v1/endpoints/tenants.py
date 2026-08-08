"""
业务接入方管理接口 — Phase 2.2：持久化到 SQLite

之前是内存 mock，现在全部走 TaskStore（harness.db tenants 表）。
stats 从 tasks 表实时聚合计算。
"""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.endpoints.auth import require_admin
from app.core.task_store import get_task_store

router = APIRouter(dependencies=[Depends(require_admin)])


# ── Pydantic 模型（与前端 API 格式完全兼容） ──

class RateLimit(BaseModel):
    qps: int = 50
    daily_cap: int = 5000


class CallStats(BaseModel):
    total_calls: int = 0
    today_calls: int = 0
    avg_latency_ms: int = 0


class TenantItem(BaseModel):
    id: int
    name: str
    team: str
    api_key: str
    status: str
    rate_limit: RateLimit
    tools_whitelist: list[str]
    contact: str = ""
    stats: CallStats
    created_at: str


class TenantCreate(BaseModel):
    name: str
    team: str
    rate_limit: RateLimit = Field(default_factory=RateLimit)
    tools_whitelist: list[str] = Field(default_factory=list)
    contact: str = ""


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    team: Optional[str] = None
    rate_limit: Optional[RateLimit] = None
    tools_whitelist: Optional[list[str]] = None
    contact: Optional[str] = None
    status: Optional[str] = None


# ── 端点 ──

@router.get("/", response_model=dict)
async def list_tenants():
    """获取业务接入方列表（含实时统计）。"""
    store = get_task_store()
    results = store.list_tenants()
    return {"count": len(results), "results": results}


@router.post("/", response_model=TenantItem)
async def create_tenant(payload: TenantCreate):
    """创建业务接入方。"""
    store = get_task_store()
    api_key = "ak-" + payload.name.lower().replace(" ", "-").replace("_", "-") + "-" + _random_key()
    rec = store.create_tenant(
        name=payload.name,
        team=payload.team,
        api_key=api_key,
        qps=payload.rate_limit.qps,
        daily_cap=payload.rate_limit.daily_cap,
        tools_whitelist=payload.tools_whitelist,
        contact=payload.contact,
    )
    return rec.to_dict()


@router.put("/{tenant_id}/", response_model=TenantItem)
async def update_tenant(tenant_id: int, payload: TenantUpdate = Body(...)):
    """更新业务接入方。"""
    store = get_task_store()
    existing = store.get_tenant(tenant_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"租户 {tenant_id} 不存在")

    kwargs = {}
    if payload.name is not None:
        kwargs["name"] = payload.name
    if payload.team is not None:
        kwargs["team"] = payload.team
    if payload.rate_limit is not None:
        kwargs["qps"] = payload.rate_limit.qps
        kwargs["daily_cap"] = payload.rate_limit.daily_cap
    if payload.tools_whitelist is not None:
        kwargs["tools_whitelist"] = payload.tools_whitelist
    if payload.contact is not None:
        kwargs["contact"] = payload.contact
    if payload.status is not None:
        kwargs["status"] = payload.status

    updated = store.update_tenant(tenant_id, **kwargs)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"租户 {tenant_id} 更新失败")
    return updated.to_dict()


@router.delete("/{tenant_id}/")
async def delete_tenant(tenant_id: int):
    """删除业务接入方。"""
    store = get_task_store()
    deleted = store.delete_tenant(tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"租户 {tenant_id} 不存在")
    return {"tenant_id": tenant_id, "status": "deleted"}


@router.post("/{tenant_id}/reset-key/", response_model=TenantItem)
async def reset_tenant_key(tenant_id: int):
    """重置 API Key。"""
    store = get_task_store()
    new_key = f"ak-{_random_key(16)}"
    updated = store.reset_tenant_api_key(tenant_id, new_key)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"租户 {tenant_id} 不存在")
    return updated.to_dict()


def _random_key(length: int = 8) -> str:
    import random
    import string
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))
