"""
可观测性中间件

- PrometheusMetricsMiddleware：记录 HTTP 请求数 + 延迟
- GracefulShutdownMiddleware：跟踪正在处理的请求，支持优雅关停
"""
import asyncio
import logging
import time
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import http_requests_total, http_request_duration_seconds

logger = logging.getLogger(__name__)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """记录请求延迟和计数，供 Prometheus 采集"""

    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path
        start = time.perf_counter()

        try:
            response: Response = await call_next(request)
            status_code = str(response.status_code)
        except Exception as exc:
            status_code = "500"
            raise
        finally:
            duration = time.perf_counter() - start
            http_request_duration_seconds.labels(method=method, path=path).observe(duration)
            http_requests_total.labels(method=method, path=path, status_code=status_code).inc()

        return response


class GracefulShutdownMiddleware(BaseHTTPMiddleware):
    """
    优雅关停中间件

    维护一个正在处理请求的计数器。
    当收到 SIGTERM 信号时，设置 _shutting_down 标志，停止接收新请求，
    并等待所有进行中的请求完成（最多 GRACEFUL_TIMEOUT_SECONDS 秒）。
    """

    GRACEFUL_TIMEOUT_SECONDS: float = 30.0

    _active_requests: int = 0
    _lock: asyncio.Lock = asyncio.Lock()
    _shutting_down: bool = False
    _shutdown_event: asyncio.Event = asyncio.Event()

    @classmethod
    def is_shutting_down(cls) -> bool:
        return cls._shutting_down

    @classmethod
    def mark_shutting_down(cls):
        cls._shutting_down = True
        logger.info("[GracefulShutdown] 收到关停信号，停止接收新请求...")

    @classmethod
    def mark_startup_complete(cls):
        """应用启动完成时复位关停标志（防御 uvicorn reload / 异常重启场景）"""
        if cls._shutting_down:
            cls._shutting_down = False
            logger.info("[GracefulShutdown] 启动完成，复位关停标志")

    @classmethod
    async def wait_for_requests(cls, timeout: Optional[float] = None):
        """等待所有活动请求处理完毕"""
        timeout = timeout or cls.GRACEFUL_TIMEOUT_SECONDS
        async with cls._lock:
            if cls._active_requests == 0:
                return
            logger.info(f"[GracefulShutdown] 等待 {cls._active_requests} 个请求完成，超时 {timeout}s")

        try:
            await asyncio.wait_for(cls._shutdown_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            async with cls._lock:
                logger.warning(f"[GracefulShutdown] 超时，仍有 {cls._active_requests} 个请求未完成")

    async def dispatch(self, request: Request, call_next):
        if self._shutting_down:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={"detail": "服务正在关停，不再接收新请求"},
                headers={"Connection": "close"},
            )

        async with self._lock:
            self._active_requests += 1
            self._shutdown_event.clear()

        try:
            response = await call_next(request)
            return response
        finally:
            async with self._lock:
                self._active_requests -= 1
                if self._active_requests == 0:
                    self._shutdown_event.set()
