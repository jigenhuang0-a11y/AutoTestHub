"""
W1.5 端到端验证测试

验证全链路：Django → 编排服务（或本地回退）→ SSE → 前端

测试覆盖：
1.  健康检查 API — 所有组件状态汇聚
2.  workflow_stream 本地执行 — SSE 事件格式 + 完整性
3.  熔断器决策链路 — 编排不可达时自动回退
4.  X-Request-ID 全链路传递
5.  错误路径验证（底座不可达时返回 HTTP 错误）
"""

import json
import time
import uuid

from django.test import TestCase
from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import User
from agent_gateway.circuit_breaker import CircuitState


class E2EHealthCheckTests(TestCase):
    """1. 健康检查 — 全组件状态汇聚"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="e2etest", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_health_returns_all_components(self):
        """health 接口应包含 LLM/CB/进度/编排 状态"""
        resp = self.client.get(reverse("agent-task-health"))
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("available_providers", data)
        self.assertIn("ai_orchestration", data)
        self.assertIn("workflow_progress", data)

        # 编排服务配置检查
        orch = data["ai_orchestration"]
        self.assertIn("url", orch)
        self.assertIn("circuit_breaker", orch)
        self.assertIn("state", orch["circuit_breaker"])

    def test_health_responds_x_request_id(self):
        """health 响应头应包含 X-Request-ID"""
        resp = self.client.get(
            reverse("agent-task-health"),
            HTTP_X_REQUEST_ID="e2e-health-001",
        )
        self.assertEqual(resp["X-Request-ID"], "e2e-health-001")


class E2EWorkflowStreamLocalTests(TestCase):
    """2. workflow_stream 本地执行 — SSE 事件流"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="e2eflow", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _collect_sse_events(self, resp) -> list:
        """从 SSE 响应中提取所有 JSON 事件"""
        events = []
        for line in resp.streaming_content:
            decoded = line.decode("utf-8") if isinstance(line, bytes) else line
            for sub_line in decoded.strip().split("\n"):
                sub_line = sub_line.strip()
                if sub_line.startswith("data:"):
                    payload_str = sub_line[5:].strip()
                    if payload_str:
                        try:
                            events.append(json.loads(payload_str))
                        except json.JSONDecodeError:
                            pass
        return events

    def test_local_workflow_stream_returns_sse(self):
        """本地工作流应返回 SSE 事件流"""
        resp = self.client.post(
            reverse("agent-task-workflow-stream"),
            {"user_request": "测试订单创建接口"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/event-stream")
        self.assertIn("X-Task-ID", resp)

        events = self._collect_sse_events(resp)
        self.assertGreater(len(events), 0, "SSE 事件流不应为空")

    def test_workflow_stream_requires_user_request(self):
        """缺少 user_request 应返回 400"""
        resp = self.client.post(
            reverse("agent-task-workflow-stream"),
            {"knowledge_base_id": 1},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_sse_events_have_expected_keys(self):
        """SSE 事件应有 event 和 data 字段"""
        resp = self.client.post(
            reverse("agent-task-workflow-stream"),
            {"user_request": "验证事件格式"},
            content_type="application/json",
        )
        events = self._collect_sse_events(resp)

        event_types = set()
        for evt in events:
            self.assertIn("event", evt, f"事件缺少 'event' 字段: {evt}")
            event_types.add(evt["event"])

        self.assertIn("workflow_complete", event_types,
                      "SSE 事件流应包含 workflow_complete 事件")

    def test_stream_response_has_x_request_id(self):
        """SSE 响应头包含 X-Request-ID（中间件自动注入）"""
        resp = self.client.post(
            reverse("agent-task-workflow-stream"),
            {"user_request": "验证 X-Request-ID"},
            content_type="application/json",
        )
        self.assertIn("X-Request-ID", resp)
        # 应为合法 UUID4
        rid = uuid.UUID(resp["X-Request-ID"])
        self.assertEqual(rid.version, 4)

    def test_passes_upstream_request_id(self):
        """上游传入的 X-Request-ID 应保持原样"""
        resp = self.client.post(
            reverse("agent-task-workflow-stream"),
            {"user_request": "验证上游 trace"},
            content_type="application/json",
            HTTP_X_REQUEST_ID="upstream-trace-999",
        )
        self.assertEqual(resp["X-Request-ID"], "upstream-trace-999")


class E2ECircuitBreakerDecisionTests(TestCase):
    """3. 熔断器决策链路 — 底座不可用时返回 503"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="e2ecircuit", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_workflow_stream_rejects_when_cb_open(self):
        """
        熔断器 OPEN 时，workflow_stream 应返回 503，
        不再有本地回退路径——底座是唯一大脑。
        """
        from agent_gateway.circuit_breaker import get_orchestration_circuit_breaker
        cb = get_orchestration_circuit_breaker(
            failure_threshold=1,
            recovery_timeout=60,
        )
        cb._state = CircuitState.OPEN
        cb._last_failure_time = time.time()

        try:
            resp = self.client.post(
                reverse("agent-task-workflow-stream"),
                {"user_request": "熔断器已断，应拒绝请求"},
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 503)
        finally:
            cb._state = CircuitState.CLOSED
            cb._failure_count = 0


class E2EXRequestIDFullChainTests(TestCase):
    """4. X-Request-ID 全链路验证"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="e2etrace", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_all_endpoints_return_x_request_id(self):
        """所有 API 端点都应返回 X-Request-ID 响应头"""
        endpoints = [
            ("GET", reverse("agent-task-health")),
            ("GET", reverse("agent-task-models")),
        ]

        for method, url, *payload in endpoints:
            if method == "GET":
                resp = self.client.get(url)
            else:
                resp = self.client.post(
                    url, payload[0], content_type="application/json"
                )

            self.assertIn(
                "X-Request-ID", resp,
                f"{method} {url} 缺少 X-Request-ID 响应头"
            )
            rid = resp["X-Request-ID"]
            self.assertTrue(len(rid) > 0, f"{method} {url} X-Request-ID 为空")

    def test_multiple_requests_have_different_ids(self):
        """不同请求应生成不同的 request_id"""
        ids = set()
        for _ in range(5):
            resp = self.client.get(reverse("agent-task-health"))
            ids.add(resp["X-Request-ID"])
        self.assertEqual(len(ids), 5, "每次请求应生成不同的 request_id")

    def test_custom_x_request_id_preserved(self):
        """自定义 X-Request-ID 在所有端点保持原样"""
        for endpoint_name, url in [
            ("health", reverse("agent-task-health")),
            ("models", reverse("agent-task-models")),
        ]:
            resp = self.client.get(url, HTTP_X_REQUEST_ID="my-custom-id")
            self.assertEqual(
                resp["X-Request-ID"], "my-custom-id",
                f"{endpoint_name} 未保持自定义 X-Request-ID"
            )


class E2EErrorFallbackTests(TestCase):
    """6. 错误回退路径"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="e2efallback", password="testpass123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @override_settings(AI_ORCHESTRATION_SERVICE_URL="http://unreachable:9999")
    def test_error_on_unreachable_orchestrator(self):
        """编排服务不可达时，workflow_stream 应返回 HTTP 错误，不再有本地回退路径"""
        resp = self.client.post(
            reverse("agent-task-workflow-stream"),
            {"user_request": "编排服务不可达，应返回错误"},
            content_type="application/json",
        )
        self.assertIn(resp.status_code, [502, 503])

    def test_invoke_requires_auth(self):
        """未认证请求应拒绝"""
        unauth_client = APIClient()
        resp = unauth_client.get(reverse("agent-task-health"))
        self.assertEqual(resp.status_code, 401)
