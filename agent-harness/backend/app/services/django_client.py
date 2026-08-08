"""
Django 业务服务客户端

编排服务通过 HTTP 调用 Django 的 Agent 网关 API。
- 全链路追踪：X-Request-ID + OpenTelemetry traceparent 透传
- 生产韧性：tenacity 重试 + 超时 + 降级
- 可观测：Prometheus metrics 埋点
"""
import contextvars
import json
import logging
from functools import wraps
from typing import Optional

import httpx
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import DJANGO_BASE_URL, security_config
from app.core.telemetry import get_tracer, inject_trace_context
from app.core.metrics import (
    django_client_requests_total,
    django_client_errors_total,
)
from app.core.security import OutputGuard

logger = logging.getLogger(__name__)

_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "orchestrator_request_id", default=""
)

tracer = get_tracer(__name__)

# 输出内容安全守卫（业务工具返回审计/脱敏）
_output_guard = OutputGuard(block_critical=security_config.output_block_critical)


def _audit_django_response(action: str, data: dict) -> dict:
    """
    对 Django 业务工具返回做安全审计：
    - 序列化整包为文本，扫描 API Key / 内网 IP / 密钥
    - 命中 critical → 脱敏为 [REDACTED]（保留可用性）
    - 命中 critical 且策略要求阻断 → 返回审计失败标记
    """
    if not security_config.output_guard_enabled:
        return data
    try:
        raw = json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        return data  # 无法序列化则跳过审计
    result = _output_guard.scan(raw)
    if result.violations:
        logger.warning(
            f"[Security] Django 返回审计命中 | action={action} | "
            f"violations={result.violations}"
        )
        if not result.is_safe:
            # 策略要求阻断：返回审计失败，不把疑似泄露内容透传给上游
            return {
                "status": "error",
                "error": f"OUTPUT_BLOCKED: {result.violations}",
                "audit_blocked": True,
            }
        # 脱敏后重建对象（保持 dict 结构）
        try:
            return json.loads(result.cleaned_text)
        except Exception:
            return data
    return data


def _get_trace_id() -> str:
    """获取当前请求上下文的 trace_id"""
    rid = _request_id_ctx.get()
    return rid if rid else "-"


def _default_retry(action: str):
    """返回下游调用通用重试装饰器"""
    return retry(
        reraise=False,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((
            requests.exceptions.RequestException,
            requests.exceptions.Timeout,
            httpx.RequestError,
            httpx.TimeoutException,
        )),
        before_sleep=lambda retry_state: logger.warning(
            f"[DjangoClient] {action} 第 {retry_state.attempt_number} 次失败，{retry_state.seconds_to_sleep:.1f}s 后重试: {retry_state.outcome.exception()}"
        ),
    )


class DjangoClient:
    """Django 下游服务客户端"""

    AGENT_ENDPOINTS = {
        "generate_testcases": "/api/agent/tasks/generate_testcases/",
        "generate_data": "/api/agent/tasks/generate_data/",
        "execute_tests": "/api/agent/tasks/execute_tests/",
        "evaluate": "/api/agent/tasks/evaluate/",
    }

    HEADER_REQUEST_ID = "X-Request-ID"

    def __init__(self, base_url: str = DJANGO_BASE_URL, auth_token: Optional[str] = None, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        # 全链路追踪：透传当前请求的 X-Request-ID
        trace_id = _get_trace_id()
        if trace_id != "-":
            headers[self.HEADER_REQUEST_ID] = trace_id
        # OpenTelemetry trace context 跨服务传播
        inject_trace_context(headers)
        return headers

    @_default_retry("call_agent")
    def call_agent(self, action: str, payload: dict) -> dict:
        """调用 Django Agent 网关 action（带重试）"""
        endpoint = self.AGENT_ENDPOINTS.get(action)
        if not endpoint:
            raise ValueError(f"未知的 Agent action: {action}")

        url = f"{self.base_url}{endpoint}"
        logger.info(f"[DjangoClient] 调用 {action}: {url}")

        with tracer.start_as_current_span("django_client.call_agent") as span:
            span.set_attribute("django.action", action)
            span.set_attribute("django.url", url)
            try:
                with requests.Session() as session:
                    resp = session.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
                    resp.raise_for_status()
                    data = resp.json()
                    status_code = str(resp.status_code)
                    django_client_requests_total.labels(action=action, status_code=status_code).inc()
                    span.set_attribute("http.status_code", resp.status_code)
                    logger.info(f"[DjangoClient] {action} 响应状态: {data.get('status', 'unknown')}")
                    # ====== 安全层：业务工具返回审计 ======
                    return _audit_django_response(action, data)
            except requests.exceptions.RequestException as e:
                django_client_errors_total.labels(action=action, error_type=type(e).__name__).inc()
                logger.error(f"[DjangoClient] 调用 {action} 失败: {e}")
                return {"status": "error", "error": f"Django 调用失败: {str(e)}"}

    @_default_retry("call_agent_async")
    async def call_agent_async(self, action: str, payload: dict) -> dict:
        """异步调用 Django Agent 网关 action（带重试）"""
        endpoint = self.AGENT_ENDPOINTS.get(action)
        if not endpoint:
            raise ValueError(f"未知的 Agent action: {action}")

        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, headers=self._headers(), json=payload)
                resp.raise_for_status()
                django_client_requests_total.labels(action=action, status_code=str(resp.status_code)).inc()
                return resp.json()
            except httpx.RequestError as e:
                django_client_errors_total.labels(action=action, error_type=type(e).__name__).inc()
                logger.error(f"[DjangoClient] 异步调用 {action} 失败: {e}")
                return {"status": "error", "error": f"Django 调用失败: {str(e)}"}

    def health(self) -> dict:
        """检查 Django 服务健康"""
        try:
            with tracer.start_as_current_span("django_client.health"):
                with requests.Session() as session:
                    resp = session.get(f"{self.base_url}/api/agent/tasks/health/", timeout=10)
                    resp.raise_for_status()
                    return resp.json()
        except Exception as e:
            django_client_errors_total.labels(action="health", error_type=type(e).__name__).inc()
            logger.error(f"[DjangoClient] Django 健康检查失败: {e}")
            return {"status": "unreachable", "error": str(e)}
