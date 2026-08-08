"""
Request ID 中间件 — 全链路追踪基础

功能：
1. 从请求头 X-Request-ID 提取上游 trace_id（若无则生成 UUID4）
2. 注入 contextvars，供日志 Filter 自动注入 LogRecord
3. 在响应头返回 X-Request-ID，前端/客户端可据此定位问题

使用 contextvars 而非 threading.local：
- Django 4.2+ 支持异步视图，contextvars 在 sync/async 下均正确
- 单一变量的存取比 threading.local 轻量
"""

import uuid
import contextvars

# 当前请求的 trace_id，由中间件在请求入口设置
_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


def get_request_id() -> str:
    """获取当前请求上下文的 trace_id（极低开销，无锁）"""
    return _request_id_ctx.get() or "-"


def set_request_id(rid: str) -> None:
    """设置当前请求上下文的 trace_id"""
    _request_id_ctx.set(rid)


class RequestIDMiddleware:
    """
    Django 中间件：在每个请求生命周期内注入 trace_id

    优先级：X-Request-ID header > 自动生成 UUID4

    注册位置：MIDDLEWARE 最顶端，确保所有后续中间件和视图
    都能通过 get_request_id() 获取到 trace_id。
    """

    HEADER_NAME = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. 从上游提取（上游可能是 Nginx / 编排服务 / 前端 SDK）
        request_id = request.META.get(
            f"HTTP_{self.HEADER_NAME.replace('-', '_').upper()}",
            "",
        ).strip()

        # 2. 上游没传则生成新的
        if not request_id:
            request_id = str(uuid.uuid4())

        # 3. 注入 contextvars 供日志 Filter 使用
        set_request_id(request_id)

        # 4. 实际处理（视图 / 下一个中间件）
        response = self.get_response(request)

        # 5. 响应头透传 trace_id
        response[self.HEADER_NAME] = request_id

        return response


class RequestIDLoggingFilter:
    """
    Python logging Filter — 自动将当前请求的 trace_id 注入 LogRecord

    用法：在 logging handler 或 logger 上添加此 filter：
        handler.addFilter(RequestIDLoggingFilter())

    LogRecord 上会多一个 `trace_id` 属性，JSON Formatter 可直接引用。
    """

    def filter(self, record: "logging.LogRecord") -> bool:
        record.trace_id = get_request_id()
        return True
