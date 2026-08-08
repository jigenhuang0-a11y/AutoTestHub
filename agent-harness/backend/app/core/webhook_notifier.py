"""
Webhook 通知调度器 — Phase 3.0

工作流完成/失败时自动向所有已启用的 Webhook 推送通知。
设计原则：fire-and-forget，不阻塞工作流主流程。
"""

import json
import hmac
import hashlib
import base64
import time
import logging
import asyncio
from typing import Optional

import httpx

from app.core.task_store import get_task_store

logger = logging.getLogger(__name__)


# ── 消息体构建（各平台适配） ──

def _build_feishu_card(
    title: str,
    title_color: str,
    fields: list[dict],
    summary: str,
    source: str,
) -> dict:
    """构建飞书交互卡片消息"""
    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": summary,
            },
        },
    ]
    # 添加详情字段
    for f in fields:
        elements.append({
            "tag": "div",
            "fields": [
                {"is_short": True, "text": {"tag": "lark_md", "content": f"**{f['label']}**"}},
                {"is_short": True, "text": {"tag": "plain_text", "content": str(f["value"])}},
            ],
        })
    elements.append({
        "tag": "hr",
    })
    elements.append({
        "tag": "note",
        "elements": [
            {"tag": "plain_text", "content": f"来自 {source} · AI 测试平台"},
        ],
    })

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": title_color,
            },
            "elements": elements,
        },
    }


def _build_dingtalk_md(title: str, summary: str, fields: list[dict], source: str) -> dict:
    """构建钉钉 Markdown 消息"""
    field_lines = "\n".join(
        f"- **{f['label']}**：{f['value']}" for f in fields
    )
    text = (
        f"## {title}\n\n"
        f"{summary}\n\n"
        f"{field_lines}\n\n"
        f"---\n"
        f"*来自 {source} · AI 测试平台*"
    )
    return {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    }


def _build_wecom_md(title: str, summary: str, fields: list[dict], source: str) -> dict:
    """构建企业微信 Markdown 消息"""
    field_lines = "\n".join(
        f">**{f['label']}**：{f['value']}" for f in fields
    )
    content = (
        f"## {title}\n\n"
        f"{summary}\n\n"
        f"{field_lines}\n"
        f"<font color=\"comment\">来自 {source} · AI 测试平台</font>"
    )
    return {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }


def _build_payload(platform: str, title: str, title_color: str,
                   fields: list[dict], summary: str, source: str) -> dict:
    """根据平台类型构建对应的消息体"""
    if platform == "feishu":
        return _build_feishu_card(title, title_color, fields, summary, source)
    elif platform == "dingtalk":
        return _build_dingtalk_md(title, summary, fields, source)
    else:  # wecom
        return _build_wecom_md(title, summary, fields, source)


def _compute_feishu_sign(secret: str) -> tuple:
    """计算飞书签名校验"""
    ts = str(int(time.time()))
    string_to_sign = f"{ts}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = base64.b64encode(hmac_code).decode("utf-8")
    return ts, sign


async def _send_to_webhook(url: str, platform: str, payload: dict,
                           secret: str = "") -> tuple[bool, str]:
    """异步发送 Webhook 消息，返回 (成功, 详情)"""
    try:
        # 飞书签名：将 timestamp 和 sign 注入 payload 顶层
        if platform == "feishu" and secret:
            ts, sign = _compute_feishu_sign(secret)
            payload = {**payload, "timestamp": ts, "sign": sign}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            body = resp.text[:300]
            if resp.status_code in (200, 204):
                logger.info(f"[WebhookNotifier] {platform} 发送成功")
                return True, f"HTTP {resp.status_code}"
            else:
                logger.warning(
                    f"[WebhookNotifier] {platform} 发送失败: HTTP {resp.status_code} - {body}"
                )
                return False, f"HTTP {resp.status_code}: {body}"
    except httpx.TimeoutException:
        return False, "请求超时（10s）"
    except httpx.ConnectError:
        return False, "无法连接目标地址"
    except Exception as e:
        logger.error(f"[WebhookNotifier] 发送异常: {e}")
        return False, str(e)


# ── 通知构建 ──

def _build_workflow_complete_notification(
    user_request: str,
    passed: bool,
    score: float,
    summary: str,
    steps_count: int,
    duration_ms: int,
    task_id: str,
) -> dict:
    """构建「工作流完成」的通知数据"""
    duration_str = f"{duration_ms / 1000:.1f}s" if duration_ms else "N/A"
    passed_count = score * steps_count if steps_count else 0

    emoji_status = "✅ 全部通过" if passed else "⚠️ 部分失败"
    title = f"🤖 测试任务完成 · {emoji_status}"
    title_color = "green" if passed else "red"

    notification_summary = (
        f"任务已执行完成，共 **{steps_count}** 个步骤，"
        f"通过 **{int(passed_count)}** 个，耗时 **{duration_str}**。"
    )

    fields = [
        {"label": "任务 ID", "value": task_id[:12] + "..." if len(task_id) > 12 else task_id},
        {"label": "用户需求", "value": user_request[:50] + ("..." if len(user_request) > 50 else "")},
        {"label": "评分", "value": f"{score * 100:.0f}%"},
        {"label": "总耗时", "value": duration_str},
    ]

    return {
        "title": title,
        "title_color": title_color,
        "fields": fields,
        "summary": f"{notification_summary}\n\n> {summary}",
    }


def _build_workflow_error_notification(
    user_request: str,
    error: str,
    task_id: str,
    retry_count: int = 0,
) -> dict:
    """构建「工作流失败」的通知数据"""
    title = "🚨 测试任务执行失败"
    title_color = "red"

    notification_summary = (
        f"任务执行过程中发生异常，当前重试次数：**{retry_count}**。"
    )

    fields = [
        {"label": "任务 ID", "value": task_id[:12] + "..." if len(task_id) > 12 else task_id},
        {"label": "用户需求", "value": user_request[:50] + ("..." if len(user_request) > 50 else "")},
        {"label": "重试次数", "value": str(retry_count)},
        {"label": "错误信息", "value": error[:80] + ("..." if len(error) > 80 else "")},
    ]

    return {
        "title": title,
        "title_color": title_color,
        "fields": fields,
        "summary": f"{notification_summary}\n\n`{error[:200]}`",
    }


# ── 调度入口 ──

async def _dispatch_notification(notification_data: dict):
    """
    向所有已启用的 Webhook 发送通知（fire-and-forget）。
    每个 Webhook 独立发送，一个失败不影响其他。
    """
    store = get_task_store()
    active_webhooks = store.get_active_webhooks()

    if not active_webhooks:
        logger.debug("[WebhookNotifier] 没有启用的 Webhook，跳过通知")
        return

    logger.info(f"[WebhookNotifier] 向 {len(active_webhooks)} 个 Webhook 发送通知")

    payload = notification_data

    for wh in active_webhooks:
        try:
            platform_payload = _build_payload(
                platform=wh.platform,
                title=payload["title"],
                title_color=payload["title_color"],
                fields=payload["fields"],
                summary=payload["summary"],
                source=wh.name,
            )
            success, detail = await _send_to_webhook(
                url=wh.url,
                platform=wh.platform,
                payload=platform_payload,
                secret=getattr(wh, "secret", ""),
            )
            if success:
                logger.info(f"[WebhookNotifier] → {wh.name}({wh.platform}) 发送成功")
            else:
                logger.warning(f"[WebhookNotifier] → {wh.name}({wh.platform}) 发送失败: {detail}")
        except Exception as e:
            logger.error(f"[WebhookNotifier] → {wh.name}({wh.platform}) 异常: {e}")


def notify_workflow_complete(
    user_request: str,
    passed: bool,
    score: float,
    summary: str,
    steps_count: int,
    duration_ms: int,
    task_id: str,
):
    """
    工作流完成时触发通知（同步调用，内部异步发送）。

    可在工作流线程中直接调用，不会阻塞主流程。
    """
    try:
        data = _build_workflow_complete_notification(
            user_request=user_request,
            passed=passed,
            score=score,
            summary=summary,
            steps_count=steps_count,
            duration_ms=duration_ms,
            task_id=task_id,
        )
        # 在新的事件循环中运行异步任务（兼容同步上下文）
        try:
            loop = asyncio.get_running_loop()
            # 已在事件循环中，创建任务不等待
            loop.create_task(_dispatch_notification(data))
        except RuntimeError:
            # 没有运行中的事件循环，用 asyncio.run
            asyncio.run(_dispatch_notification(data))
    except Exception as e:
        logger.error(f"[WebhookNotifier] 通知构建/发送异常: {e}")


def notify_workflow_error(
    user_request: str,
    error: str,
    task_id: str,
    retry_count: int = 0,
):
    """
    工作流失败时触发通知（同步调用，内部异步发送）。
    """
    try:
        data = _build_workflow_error_notification(
            user_request=user_request,
            error=error,
            task_id=task_id,
            retry_count=retry_count,
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_dispatch_notification(data))
        except RuntimeError:
            asyncio.run(_dispatch_notification(data))
    except Exception as e:
        logger.error(f"[WebhookNotifier] 通知构建/发送异常: {e}")
