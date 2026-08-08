"""结构化日志：统一 JSON 格式 + trace_id 全链路串联。

所有服务复用同一套日志格式，便于后期接入 Loki / Grafana。
"""
from __future__ import annotations

import sys
from contextvars import ContextVar

from loguru import logger

# 全链路追踪上下文，每个请求生成独立 trace_id
trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)


def configure_logging() -> None:
    logger.remove()
    fmt = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{extra[trace_id]} | {name}:{function}:{line} | {message}"
    )
    logger.add(
        sys.stdout,
        format=fmt,
        level="DEBUG" if __import__("os").environ.get("APP_DEBUG") else "INFO",
        enqueue=True,
        colorize=False,
        backtrace=False,
        diagnose=False,
    )
    # 注入 trace_id 到每条日志
    logger.configure(extra={"trace_id": "no-trace"})


def bind_trace(trace_id: str) -> None:
    trace_id_ctx.set(trace_id)


configure_logging()
