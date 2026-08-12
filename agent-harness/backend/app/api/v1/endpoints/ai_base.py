"""
AI 底座 / 模型配置 API。

暴露 task_store 中的 model_configs，供前端「AI 底座配置」页面以及
用例生成 / 数据工厂 / 接口调试等需要真实 LLM 能力的模块选择模型、拉取激活模型。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.v1.endpoints.auth import get_current_user as require_auth
from app.core.task_store import get_task_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-base", tags=["ai-base"])


class ModelConfigBase(BaseModel):
    name: str = ""
    provider: str = ""
    description: str = ""
    is_enabled: bool = True
    base_url: str = ""
    api_key_placeholder: str = ""


class ModelConfigCreate(ModelConfigBase):
    pass


class ModelConfigPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    is_enabled: bool | None = None
    base_url: str | None = None
    api_key_placeholder: str | None = None


@router.get("/models/")
async def list_models(_: None = Depends(require_auth)):
    """列出全部模型配置"""
    store = get_task_store()
    rows = store.list_models()
    return {"items": [r.to_dict() for r in rows], "total": len(rows)}


@router.get("/models/active/")
async def get_active_model(_: None = Depends(require_auth)):
    """返回当前默认启用的模型（测试模块走真实底座时使用）"""
    store = get_task_store()
    rec = store.get_active_model()
    if not rec:
        raise HTTPException(status_code=404, detail="未配置任何模型")
    return rec.to_dict()


@router.post("/models/")
async def create_model(payload: ModelConfigCreate, _: None = Depends(require_auth)):
    """新增模型配置"""
    store = get_task_store()
    data = payload.model_dump()
    from datetime import datetime, timezone
    data["created_at"] = datetime.now(timezone.utc).isoformat()
    rec = store.create_model_config(data)
    return rec.to_dict()


@router.patch("/models/{model_id}/")
async def patch_model(model_id: int, payload: ModelConfigPatch, _: None = Depends(require_auth)):
    """局部更新模型配置（启用/禁用、base_url 等）"""
    store = get_task_store()
    rec = store.update_model_config(model_id, payload.model_dump(exclude_unset=True))
    if not rec:
        raise HTTPException(status_code=404, detail="模型不存在")
    return rec.to_dict()


@router.post("/models/{model_id}/test_connection/")
async def test_connection(model_id: int, _: None = Depends(require_auth)):
    """探测该模型对应 provider 是否可用（无 Key 时返回不可用的原因）"""
    store = get_task_store()
    rec = store.get_model_config_by_id(model_id)
    if not rec:
        raise HTTPException(status_code=404, detail="模型不存在")
    from app.core.config import get_available_providers
    available = get_available_providers()
    ok = rec.provider in available
    return {
        "ok": ok,
        "provider": rec.provider,
        "reason": None if ok else f"Provider '{rec.provider}' 未配置 API Key（请在 .env 中设置 {rec.provider.upper()}_API_KEY）",
    }
