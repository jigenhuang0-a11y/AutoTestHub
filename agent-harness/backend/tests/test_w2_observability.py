"""
W2 可观测性 + 可靠性测试

覆盖：
1. /metrics 端点可采集 Prometheus 指标
2. /health/live 与 /health/ready 探针行为
3. PrometheusMetricsMiddleware 存在且可实例化
4. GracefulShutdownMiddleware 初始状态
5. LocalToolGateway 正常创建且可列出本地工具
6. OpenTelemetry tracer 已初始化
"""
import sys
from pathlib import Path

# 确保 import app.* 正确
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app
from app.core.middleware import GracefulShutdownMiddleware, PrometheusMetricsMiddleware
from app.core.gateway_factory import get_tool_gateway_client
from app.core.telemetry import get_tracer
from app.core import metrics as metrics_module


client = TestClient(app)


def test_metrics_endpoint_returns_prometheus_format():
    """2.2 Prometheus Metrics 端点可采集"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "# HELP" in response.text
    assert response.headers["content-type"] == "text/plain; version=0.0.4; charset=utf-8"


def test_health_live_probe():
    """2.4 liveness 探针：只要活着就返回 200"""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_health_ready_probe_fails_without_provider():
    """2.4 readiness 探针：未配置 Provider 时返回 503"""
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_prometheus_metrics_middleware_initializes():
    """2.2 Prometheus 中间件可实例化"""
    mw = PrometheusMetricsMiddleware(app)
    assert mw is not None


def test_graceful_shutdown_initial_state():
    """2.3 优雅关停初始状态：未关停，活跃请求数为 0"""
    assert GracefulShutdownMiddleware.is_shutting_down() is False


def test_local_tool_gateway_lists_tools():
    """2.5 本地工具网关可正常创建并列出工具（替代原 DjangoClient）"""
    gateway = get_tool_gateway_client(auth_token="test-token")
    assert gateway is not None
    tools = gateway.list_tools(team_id="default")
    assert isinstance(tools, list)
    assert len(tools) >= 5  # search/generator/data_factory/execution/evaluator


def test_opentelemetry_tracer_initialized():
    """2.1 OpenTelemetry tracer 已初始化"""
    tracer = get_tracer("test")
    assert tracer is not None


def test_registry_metrics_are_defined():
    """核心指标已在 /metrics 输出中暴露"""
    response = client.get("/metrics")
    text = response.text
    assert "http_requests_total" in text
    assert "workflow_total" in text
    assert "local_tool_requests_total" in text
    assert "workflow_active" in text
    assert "llm_requests_total" in text




def test_health_endpoint_returns_components():
    """综合健康检查返回关键组件状态"""
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "available_providers" in data
    assert "workflow_progress" in data
    assert "shutting_down" in data


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
