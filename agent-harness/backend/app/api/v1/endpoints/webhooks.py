"""
Webhook 通知配置 API — Phase 2.5

提供 Webhook 配置的 CRUD 和测试发送能力。
"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.endpoints.auth import require_non_viewer
from pydantic import BaseModel, Field

from app.core.task_store import get_task_store

router = APIRouter(tags=["Webhooks"])


# ── Request Schemas ──

class WebhookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Webhook 名称")
    platform: str = Field(..., description="平台: feishu / dingtalk / wecom")
    url: str = Field(..., min_length=1, description="Webhook URL")
    active: bool = Field(default=True, description="是否启用")


class WebhookUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    platform: str | None = None
    url: str | None = None
    active: bool | None = None


class WebhookTest(BaseModel):
    message: str = Field(default="这是一条来自 AI 测试平台的测试通知 🚀",
                         description="测试消息内容")


# ── Endpoints ──

@router.get("/")
async def list_webhooks():
    """获取所有 Webhook 配置"""
    store = get_task_store()
    webhooks = store.list_webhooks()
    return {"results": webhooks, "count": len(webhooks)}


@router.get("/{wh_id}")
async def get_webhook(wh_id: str):
    """获取单个 Webhook 配置"""
    store = get_task_store()
    wh = store.get_webhook(wh_id)
    if not wh:
        raise HTTPException(status_code=404, detail=f"Webhook {wh_id} 不存在")
    return {"data": wh.to_dict()}


@router.post("/", status_code=201)
async def create_webhook(body: WebhookCreate, user: dict = Depends(require_non_viewer)):
    """新增 Webhook 配置"""
    store = get_task_store()
    wh = store.create_webhook(
        name=body.name,
        platform=body.platform,
        url=body.url,
        active=body.active,
    )
    return {"data": wh.to_dict(), "message": "Webhook 已添加"}


@router.patch("/{wh_id}")
async def update_webhook(wh_id: str, body: WebhookUpdate, user: dict = Depends(require_non_viewer)):
    """更新 Webhook 配置"""
    store = get_task_store()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="至少需要一个更新字段")
    wh = store.update_webhook(wh_id, **updates)
    if not wh:
        raise HTTPException(status_code=404, detail=f"Webhook {wh_id} 不存在")
    return {"data": wh.to_dict(), "message": "Webhook 已更新"}


@router.delete("/{wh_id}")
async def delete_webhook(wh_id: str, user: dict = Depends(require_non_viewer)):
    """删除 Webhook 配置"""
    store = get_task_store()
    if not store.delete_webhook(wh_id):
        raise HTTPException(status_code=404, detail=f"Webhook {wh_id} 不存在")
    return {"message": f"Webhook {wh_id} 已删除"}


@router.post("/{wh_id}/test")
async def test_webhook(wh_id: str, body: WebhookTest = WebhookTest(), user: dict = Depends(require_non_viewer)):
    """测试发送一条通知到目标 Webhook"""
    store = get_task_store()
    wh = store.get_webhook(wh_id)
    if not wh:
        raise HTTPException(status_code=404, detail=f"Webhook {wh_id} 不存在")
    if not wh.active:
        raise HTTPException(status_code=400, detail="Webhook 已停用，请先启用")

    success, detail = await _send_webhook(wh, body.message)
    if success:
        return {"message": "测试通知发送成功", "detail": detail}
    else:
        raise HTTPException(
            status_code=502,
            detail=f"发送失败: {detail}"
        )


# ── 发送逻辑 ──

import json
import logging
import httpx

logger = logging.getLogger(__name__)


def _build_platform_payload(wh, message: str) -> dict:
    """构建各平台的通知体"""
    if wh.platform == "feishu":
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "🤖 AI 测试平台通知"},
                    "template": "blue",
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": message}},
                    {
                        "tag": "note",
                        "elements": [
                            {"tag": "plain_text", "content": f"来自 {wh.name} · {wh.created_at[:10]}"}
                        ],
                    },
                ],
            },
        }
    elif wh.platform == "dingtalk":
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": "AI 测试平台通知",
                "text": f"## 🤖 AI 测试平台通知\n\n{message}\n\n---\n*来自 {wh.name}*",
            },
        }
    else:  # wecom (企业微信)
        return {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## 🤖 AI 测试平台通知\n\n{message}\n\n<font color=\"comment\">来自 {wh.name}</font>",
            },
        }


async def _send_webhook(wh, message: str) -> tuple[bool, str]:
    """异步发送 Webhook 通知，返回 (成功, 详情)"""
    payload = _build_platform_payload(wh, message)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(wh.url, json=payload)
            body = resp.text[:300]
            if resp.status_code in (200, 204):
                logger.info(f"[Webhook] {wh.name}({wh.platform}) 发送成功")
                return True, f"HTTP {resp.status_code}"
            else:
                logger.warning(f"[Webhook] {wh.name} 发送失败: HTTP {resp.status_code} - {body}")
                return False, f"HTTP {resp.status_code}: {body}"
    except httpx.TimeoutException:
        return False, "请求超时（10s）"
    except httpx.ConnectError:
        return False, "无法连接目标地址"
    except Exception as e:
        logger.error(f"[Webhook] 发送异常: {e}")
        return False, str(e)
