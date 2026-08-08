"""
Prometheus Metrics 配置

W2 目标：/metrics 可采集
- http_requests_total：HTTP 请求总数（按方法、路径、状态码分）
- http_request_duration_seconds：HTTP 请求延迟直方图
- workflow_total：工作流调用总数（按状态分）
- workflow_step_duration_seconds：工作流单步执行耗时
- local_tool_requests_total：本地工具调用总数（按工具名、状态分）
- local_tool_errors_total：本地工具调用错误数（按工具名、异常类型分）
- active_workflows：当前正在执行的工作流数量（Gauge）
"""
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
)

# 使用独立注册表，避免与默认全局注册表冲突（FastAPI 多进程场景）
REGISTRY = CollectorRegistry()

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
    registry=REGISTRY,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    registry=REGISTRY,
)

workflow_total = Counter(
    "workflow_total",
    "Total workflow invocations",
    ["status", "mode"],  # status: started/completed/failed; mode: sync/stream
    registry=REGISTRY,
)

workflow_step_duration_seconds = Histogram(
    "workflow_step_duration_seconds",
    "Workflow single step duration in seconds",
    ["agent"],
    registry=REGISTRY,
)

workflow_active = Gauge(
    "workflow_active",
    "Number of active workflows",
    registry=REGISTRY,
)

local_tool_requests_total = Counter(
    "local_tool_requests_total",
    "Total requests to local tools",
    ["action", "status_code"],
    registry=REGISTRY,
)

local_tool_errors_total = Counter(
    "local_tool_errors_total",
    "Total errors when calling local tools",
    ["action", "error_type"],
    registry=REGISTRY,
)

llm_requests_total = Counter(
    "llm_requests_total",
    "Total LLM requests",
    ["provider", "model", "status"],
    registry=REGISTRY,
)

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["provider", "model"],
    registry=REGISTRY,
)

# ---- Supervisor-Worker 多代理编排指标 ----
supervisor_decisions_total = Counter(
    "supervisor_worker_decisions_total",
    "Supervisor dispatched worker executions",
    ["worker", "status"],  # worker: search/generator/...; status: completed/failed
    registry=REGISTRY,
)

supervisor_worker_duration_seconds = Histogram(
    "supervisor_worker_duration_seconds",
    "Single worker execution duration in seconds under Supervisor",
    ["worker"],
    registry=REGISTRY,
)


def metrics_response() -> tuple:
    """返回 Prometheus 采集格式的响应体与 Content-Type"""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
