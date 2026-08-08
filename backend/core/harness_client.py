"""Agent Harness 客户端：优先走统一编排底座，失败时降级到本地直连。"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterable, List, Mapping

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

def _base_url() -> str:
    return getattr(settings, "AI_ORCHESTRATION_SERVICE_URL", os.getenv("AI_ORCHESTRATION_SERVICE_URL", "http://localhost:8001"))


def _service_token() -> str:
    return getattr(settings, "SERVICE_TOKEN", os.getenv("SERVICE_TOKEN", ""))


def _timeout() -> float:
    return float(getattr(settings, "HARNESS_TIMEOUT", os.getenv("HARNESS_TIMEOUT", "30")))


def _normalize_messages(messages: List[Any]) -> List[Mapping[str, str]]:
    """把 LangChain 消息对象或 dict 统一转成 OpenAI 风格的 dict list。"""
    normalized: List[Mapping[str, str]] = []
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get("role") or getattr(msg, "type", "user")
            content = msg.get("content") or ""
            normalized.append({"role": role, "content": content})
        elif hasattr(msg, "type") and hasattr(msg, "content"):
            # LangChain BaseMessage
            normalized.append({"role": msg.type, "content": msg.content})
        else:
            normalized.append({"role": "user", "content": str(msg)})
    return normalized


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    token = _service_token()
    if token:
        headers["X-Service-Token"] = token
    return headers


def harness_chat(messages: List[Any], model: str | None = None, task_type: str = "knowledge_base") -> str:
    """同步调用 Agent Harness LLM，失败返回空字符串。"""
    try:
        payload = {
            "messages": _normalize_messages(messages),
            "task_type": task_type,
            "model": model,
        }
        resp = requests.post(
            f"{_base_url()}/api/v1/llm/chat",
            headers=_headers(),
            json=payload,
            timeout=_timeout(),
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("answer") or data.get("content") or data.get("response")
        if answer:
            logger.info(f"[HarnessClient] chat 成功，model={data.get('model_used')}")
            return answer
    except Exception as e:
        logger.warning(f"[HarnessClient] chat 失败，将降级: {e}")
    return ""


def harness_chat_stream(messages: List[Any], model: str | None = None, task_type: str = "knowledge_base",
                        max_tokens: int = 2000) -> Iterable[str]:
    """流式调用 Agent Harness LLM，失败时 yield 空字符串作为失败标记。"""
    try:
        payload = {
            "messages": _normalize_messages(messages),
            "task_type": task_type,
            "model": model,
            "max_tokens": max_tokens,
        }
        resp = requests.post(
            f"{_base_url()}/api/v1/llm/chat/stream",
            headers=_headers(),
            json=payload,
            timeout=_timeout(),
            stream=True,
        )
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data_str = line[len("data: "):].strip()
            if not data_str:
                continue
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            if data.get("done"):
                break
            if data.get("error"):
                logger.warning(f"[HarnessClient] stream 服务端错误: {data['error']}")
                break
            chunk = data.get("chunk")
            if chunk:
                yield chunk
        return
    except Exception as e:
        logger.warning(f"[HarnessClient] stream 失败，将降级: {e}")
    # 失败标记：消费端检测到空串后可切本地
    yield ""
