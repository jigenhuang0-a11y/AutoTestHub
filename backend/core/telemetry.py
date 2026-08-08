"""
OpenTelemetry 链路追踪 — Django 侧初始化与 Context 注入

职责：
1. 启动时初始化 TracerProvider + W3C TraceContext 传播器
2. 提供 inject_context()，在转发 HTTP 请求到底座前将 trace context 注入请求头
3. 底座 FastAPI 的 Instrumentor 会自动提取 traceparent → 建立父子 Span 关联

链路关系：
  前端 X-Request-ID
    → Django Span（agent_gateway.invoke）
      → [inject traceparent] → HTTP请求头
        → 底座 Span（llm.chat / workflow.run）
          → LLM API Span（DeepSeek调用）
"""

import logging
from typing import Dict

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.propagate import inject
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .middleware import get_request_id

logger = logging.getLogger(__name__)

# 服务名
OTEL_SERVICE_NAME = "ai-test-platform-django"


def setup_telemetry() -> TracerProvider:
    """
    初始化 OpenTelemetry TracerProvider。

    在 Django settings.py 末尾调用一次即可。
    开发环境：ConsoleSpanExporter（终端输出 Span）
    生产环境：通过 OTEL_EXPORTER_OTLP_ENDPOINT 环境变量自动激活 OTLP 导出
    """
    resource = Resource.create({
        SERVICE_NAME: OTEL_SERVICE_NAME,
        SERVICE_VERSION: "1.0.0",
    })

    provider = TracerProvider(resource=resource)

    # 开发环境：Console 导出器（终端实时查看 Trace）
    console_exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # 生产环境：OTLP 导出器（仅在 OTEL_EXPORTER_OTLP_ENDPOINT 环境变量存在时启用）
    import os as _os
    if _os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            otlp_exporter = OTLPSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info("[OTel] OTLP exporter configured → %s", _os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
        except Exception as e:
            logger.warning("[OTel] OTLP exporter setup failed (develop mode ok): %s", e)

    # 全局设置
    trace.set_tracer_provider(provider)

    # 全局传播器：W3C TraceContext（底座 FastAPI 默认支持）
    # 不设则不会向传出 HTTP 注入 traceparent
    from opentelemetry.propagate import set_global_textmap
    set_global_textmap(TraceContextTextMapPropagator())

    logger.info(f"[OTel] Telemetry initialized for service={OTEL_SERVICE_NAME}")
    return provider


def get_tracer(name: str = "agent_gateway") -> trace.Tracer:
    """获取 tracer 实例。"""
    return trace.get_tracer(name)


def inject_context(headers: Dict[str, str] = None) -> Dict[str, str]:
    """
    将当前 OTel Span 的 trace context 注入 HTTP 请求头。

    用法：
        headers = inject_context({"Content-Type": "application/json"})
        requests.post("http://localhost:8001/...", json=payload, headers=headers)

    注入的头：
        traceparent: 00-{trace_id}-{span_id}-01
        tracestate: （如有）
    """
    if headers is None:
        headers = {}

    # inject 将当前活动的 Span context 写入 headers
    inject(headers)

    # 同时透传业务 X-Request-ID，保持业务 trace 和 OTel trace 关联
    rid = get_request_id()
    if rid and rid != "-":
        headers.setdefault("X-Request-ID", rid)

    return headers
