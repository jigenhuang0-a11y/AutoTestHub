"""
OpenTelemetry Trace 配置

W2 目标：调用链可视化
- 自动追踪 FastAPI 请求
- 手动在工作流关键节点埋点
- 支持 OTLP 导出（可配置）和 Console 导出（开发调试）
"""
import os
import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION, DEPLOYMENT_ENVIRONMENT
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.propagate import set_global_textmap

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    _OTLP_AVAILABLE = True
except ImportError as _e:
    OTLPSpanExporter = None
    _OTLP_AVAILABLE = False

logger = logging.getLogger(__name__)

OTLP_ENABLED = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "ai-orchestration-service")
OTEL_ENVIRONMENT = os.getenv("OTEL_ENVIRONMENT", "development")


def setup_tracer_provider() -> TracerProvider:
    """初始化 TracerProvider，全局只应调用一次"""
    resource = Resource.create({
        SERVICE_NAME: OTEL_SERVICE_NAME,
        SERVICE_VERSION: os.getenv("OTEL_SERVICE_VERSION", "0.1.0"),
        DEPLOYMENT_ENVIRONMENT: OTEL_ENVIRONMENT,
        "host.name": os.getenv("HOSTNAME", os.getenv("COMPUTER_NAME", "unknown")),
    })

    provider = TracerProvider(resource=resource)

    if OTLP_ENABLED and _OTLP_AVAILABLE:
        try:
            exporter = OTLPSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(f"[Telemetry] OTLP exporter enabled: {OTLP_ENABLED}")
        except Exception as e:
            logger.warning(f"[Telemetry] OTLP exporter failed: {e}, fallback to console")
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        # 开发环境默认输出到控制台，方便观察
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        if not _OTLP_AVAILABLE:
            logger.info("[Telemetry] OTLP exporter unavailable, console exporter enabled")
        else:
            logger.info("[Telemetry] Console exporter enabled (set OTEL_EXPORTER_OTLP_ENDPOINT for OTLP)")

    trace.set_tracer_provider(provider)
    # 使用 W3C TraceContext 作为全局传播器（兼容 HTTP Header）
    set_global_textmap(TraceContextTextMapPropagator())
    return provider


def get_tracer(name: str = __name__):
    """获取 tracer 实例"""
    return trace.get_tracer(name)


def inject_trace_context(headers: dict) -> dict:
    """将当前 span 的 trace context 注入到 HTTP headers 中，用于跨服务传播"""
    propagator = TraceContextTextMapPropagator()
    propagator.inject(carrier=headers)
    return headers
