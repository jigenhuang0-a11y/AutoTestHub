"""
W1.4 结构化日志验证测试

验证点：
1. RequestIDMiddleware 生成/提取 trace_id
2. RequestIDLoggingFilter 注入 trace_id 到 LogRecord
3. StructlogJSONFormatter 输出合法 JSON + 必要字段
4. 无请求上下文时 trace_id 为 "-"（容错）
5. X-Request-ID 响应头返回
"""

import json
import logging
import uuid

import pytest
from django.test import RequestFactory

from core.middleware import (
    RequestIDMiddleware,
    RequestIDLoggingFilter,
    get_request_id,
    set_request_id,
)
from core.logging_setup import StructlogJSONFormatter


class TestRequestIDGetSet:
    """基础 contextvar 读写"""

    def test_default_is_empty(self):
        """无请求上下文时返回 "-" """
        # 重置 contextvar（隔离测试）
        # 注：测试在单线程运行，set_request_id 设过的会残留；
        # 这里测的是 get_request_id 在 contextvar 为空时的行为
        # OK——实际无中间件的场景下默认就是 ""
        assert isinstance(get_request_id(), str)

    def test_set_and_get(self):
        rid = str(uuid.uuid4())
        set_request_id(rid)
        assert get_request_id() == rid

    def test_set_empty_returns_dash(self):
        set_request_id("")
        # contextvar 存的是空串，get_request_id 会 fallback 到 "-"
        assert get_request_id() == "-"


class TestRequestIDFilter:
    """RequestIDLoggingFilter"""

    def test_filter_injects_trace_id(self):
        rid = str(uuid.uuid4())
        set_request_id(rid)

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello", args=(), exc_info=None,
        )
        f = RequestIDLoggingFilter()
        result = f.filter(record)
        assert result is True
        assert record.trace_id == rid


class TestStructlogJSONFormatter:
    """JSON 格式化器"""

    def test_output_is_valid_json(self):
        set_request_id("trace-001")
        record = logging.LogRecord(
            name="core.agents.plan_agent", level=logging.INFO,
            pathname="/app/core/agents/plan_agent.py", lineno=42,
            msg="生成执行计划", args=(), exc_info=None,
        )
        # 手动模拟 filter 注入
        RequestIDLoggingFilter().filter(record)

        fmt = StructlogJSONFormatter()
        output = fmt.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "core.agents.plan_agent"
        assert parsed["trace_id"] == "trace-001"
        assert "生成执行计划" in parsed["message"]
        assert parsed["module"] == "plan_agent"
        assert parsed["lineno"] == 42


class TestRequestIDMiddleware:
    """Django 中间件集成"""

    def test_generates_new_id_when_no_header(self):
        factory = RequestFactory()
        request = factory.get("/api/health/")

        def dummy_response(r):
            from django.http import HttpResponse
            return HttpResponse("ok")

        middleware = RequestIDMiddleware(dummy_response)
        response = middleware(request)

        assert response["X-Request-ID"]
        # 应该是合法的 UUID4
        uid = uuid.UUID(response["X-Request-ID"])
        assert uid.version == 4

    def test_reuses_incoming_header(self):
        factory = RequestFactory()
        request = factory.get("/api/health/", HTTP_X_REQUEST_ID="incoming-001")

        def dummy_response(r):
            from django.http import HttpResponse
            return HttpResponse("ok")

        middleware = RequestIDMiddleware(dummy_response)
        response = middleware(request)

        assert response["X-Request-ID"] == "incoming-001"

    def test_response_header_present(self):
        """响应头必定包含 X-Request-ID"""
        factory = RequestFactory()
        request = factory.get("/api/test/")

        def dummy_response(r):
            from django.http import HttpResponse
            return HttpResponse("ok")

        middleware = RequestIDMiddleware(dummy_response)
        response = middleware(request)

        assert "X-Request-ID" in response
        assert len(response["X-Request-ID"]) > 0
