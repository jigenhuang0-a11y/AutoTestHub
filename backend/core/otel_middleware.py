"""
OpenTelemetry Django 中间件 — 自动为每个 HTTP 请求创建 Span

链路：
  前端请求
    → Django Middleware Span（自动创建，携带 X-Request-ID）
      → agent_gateway Span（views.py 手动创建）
        → [inject traceparent] → 底座 FastAPI Span
          → LLM API Span
"""

import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class OTelTracingMiddleware(MiddlewareMixin):
    """
    为每个 HTTP 请求自动创建 OTel Span。

    注意：
    - Span 在 process_view 中创建（此时能拿到 view 名称）
    - Span 在 process_response 中结束
    - inject_context() 依赖此 Span 的存在
    - 不做 W3C TraceContext 提取（生产环境由 Nginx/Gateway 注入更标准的 traceparent）
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        """在抵达 view 之前创建 Span。"""
        try:
            from opentelemetry import trace
            tracer = trace.get_tracer("django.http")

            span_name = f"{request.method} {request.path}"
            tags = {
                "http.method": request.method,
                "http.url": request.build_absolute_uri(),
                "http.scheme": request.scheme,
                "component": "django",
            }

            # 关联业务 RequestID
            rid = getattr(request, 'request_id', None)
            if rid:
                tags["x_request_id"] = rid

            span = tracer.start_span(span_name, attributes=tags)

            # 设为当前活动的 Span（inject_context 会读取它）
            from opentelemetry import context
            ctx = trace.set_span_in_context(span)
            token = context.attach(ctx)

            # 存入 request 对象，供 process_response 使用
            request._otel_span = span
            request._otel_token = token

        except Exception:
            # OTel 不应该影响正常请求
            pass

    def process_response(self, request, response):
        """请求结束时结束 Span。"""
        try:
            from opentelemetry import context

            span = getattr(request, '_otel_span', None)
            token = getattr(request, '_otel_token', None)

            if span is not None:
                span.set_attribute("http.status_code", response.status_code)
                span.end()

            if token is not None:
                context.detach(token)

        except Exception:
            pass

        return response

    def process_exception(self, request, exception):
        """请求抛异常时记录错误。"""
        try:
            span = getattr(request, '_otel_span', None)
            if span is not None:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(exception))
                span.record_exception(exception)
                span.set_status(
                    trace.StatusCode.ERROR,
                    str(exception)[:255]
                )
        except Exception:
            pass
