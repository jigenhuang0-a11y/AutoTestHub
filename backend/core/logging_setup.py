"""
结构化日志配置工具

提供：
1. StructlogJSONFormatter — 标准 logging Formatter，输出 JSON 一行一条
2. configure_structured_logging() — 一键注入全局 Filter，确保所有 handler 都支持 trace_id
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .middleware import RequestIDLoggingFilter


def _default_serializer(obj: Any) -> Any:
    """处理 datetime / set 等 JSON 不支持的类型"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return str(obj)


class StructlogJSONFormatter(logging.Formatter):
    """
    JSON 结构化日志格式

    每行一条 JSON，包含以下字段：
    - timestamp: ISO 8601 带毫秒
    - level: 日志级别
    - logger: logger 名称（如 core.agents.plan_agent）
    - trace_id: 全链路追踪 ID（无请求上下文时为 "-"）
    - message: 日志正文
    - module: 源模块
    - funcName: 函数名
    - lineno: 行号
    - exc_info: 异常信息（如有）

    可通过 LOG_FORMAT_EXTRA_KEYS 环境变量添加自定义 key。
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "trace_id": getattr(record, "trace_id", "-"),
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }

        if record.exc_info and record.exc_info[0]:
            log_entry["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=_default_serializer, ensure_ascii=False)


# 全局 Filter 实例，只需创建一次
_global_request_id_filter = RequestIDLoggingFilter()


def inject_request_id_filter():
    """
    给所有已有 handler 注入 RequestIDFilter

    在 Django ready() 信号中调用，确保自定义 App 的 logger
    以及 django 自带的 handler 都能拿到 trace_id。
    """
    for logger_name in ("", "django", "django.request", "django.server"):
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            if _global_request_id_filter not in handler.filters:
                handler.addFilter(_global_request_id_filter)
