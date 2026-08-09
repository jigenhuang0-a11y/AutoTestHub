"""
Webhook 通知发送器（Phase 2.5 真正触发）

之前 webhook_configs 表只能 CRUD，没有任何地方真正发送通知。
本模块在以下事件触发时，向所有启用的 Webhook 推送消息：
  - workflow_start   工作流启动
  - workflow_success 工作流成功完成
  - workflow_failed  工作流失败（含自愈失败）
  - safety_rejected  代码安全检查拒绝

支持飞书 / 钉钉 / 企业微信。发送失败仅记录日志，不影响主流程。
"""

import hashlib
import hmac
import json
import logging
import time
import urllib.request
from typing import Optional

from app.core.task_store import get_task_store, WebhookRecord

logger = logging.getLogger(__name__)


def _sign_feishu(secret: str, timestamp: int) -> str:
    """飞书自定义机器人签名：HMAC-SHA256(base_string, secret) 后 base64"""
    import base64
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def _build_payload(wh: WebhookRecord, text: str) -> dict:
    ts = int(time.time())
    if wh.platform == "feishu":
        body = {"msg_type": "text", "content": {"text": text}}
        if wh.secret:
            body["timestamp"] = str(ts)
            body["sign"] = _sign_feishu(wh.secret, ts)
        return body
    if wh.platform == "dingtalk":
        body = {"msgtype": "text", "text": {"content": text}}
        if wh.secret:
            # 钉钉签名需要 timestamp + secret 的 HMAC（毫秒级）
            import hashlib as _h
            string_to_sign = f"{ts}{wh.secret}"
            sign = _h.sha256(string_to_sign.encode("utf-8")).hexdigest()
            body["timestamp"] = str(ts)
            body["sign"] = sign
        return body
    # 企业微信
    return {"msgtype": "text", "text": {"content": text}}


def _post(wh: WebhookRecord, text: str) -> bool:
    try:
        body = _build_payload(wh, text)
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            wh.url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        logger.warning(f"[Webhook] 推送 {wh.name}({wh.platform}) 失败: {e}")
        return False


def dispatch_webhook_event(event_type: str, payload: dict) -> int:
    """
    向所有启用的 Webhook 推送一条事件通知。
    返回成功推送的数量（失败静默忽略）。
    """
    try:
        whs = get_task_store().get_active_webhooks()
    except Exception as e:
        logger.warning(f"[Webhook] 读取配置失败: {e}")
        return 0
    if not whs:
        return 0

    title = {
        "workflow_start": "🔵 工作流启动",
        "workflow_success": "🟢 工作流完成",
        "workflow_failed": "🔴 工作流失败",
        "safety_rejected": "⚠️ 代码安全检查拒绝",
    }.get(event_type, event_type)

    lines = [f"{title}"]
    for k, v in payload.items():
        if isinstance(v, (str, int, float, bool)) and v not in ("", None):
            lines.append(f"- {k}: {v}")
    text = "\n".join(lines)

    ok = 0
    for wh in whs:
        if _post(wh, text):
            ok += 1
    if ok:
        logger.info(f"[Webhook] 事件 {event_type} 已推送 {ok}/{len(whs)} 个 Webhook")
    return ok
