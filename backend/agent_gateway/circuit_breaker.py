"""
Circuit Breaker — AI 编排服务熔断回退机制

实现标准三态熔断器：
- CLOSED（闭合）：远程服务正常，请求走编排服务。
- OPEN（断开）：连续失败达到阈值，直接本地执行，避免拖垮 Django。
- HALF_OPEN（半开）：熔断超时后，允许一次试探请求，成功则 CLOSED，失败则 OPEN。

线程安全：使用 RLock 保护状态变更，适用于多 worker Gunicorn 进程内多线程。
"""
import time
import logging
import threading
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    简易熔断器，用于保护 Django 对独立 AI 编排服务的调用。

    参数：
        failure_threshold: 连续失败多少次后熔断（默认 5）
        recovery_timeout: 熔断后经过多少秒进入半开状态（默认 60）
        half_open_max_calls: 半开状态下允许多少次试探请求（默认 1）
        expected_exception: 触发失败的异常类型元组（默认 Exception）
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
        expected_exception: tuple = (Exception,),
        name: str = "orchestrator",
    ):
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_timeout = max(0.0, float(recovery_timeout))
        self.half_open_max_calls = max(1, half_open_max_calls)
        self.expected_exception = expected_exception
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    @property
    def state_label(self) -> str:
        return self.state.value

    def can_call(self) -> bool:
        """
        判断当前是否允许调用远程服务。
        如果处于 OPEN 状态且未超过 recovery_timeout，返回 False。
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    self._failure_count = 0
                    logger.info(
                        f"[CircuitBreaker:{self.name}] 熔断超时 ({elapsed:.0f}s)，进入半开状态"
                    )
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                return self._success_count < self.half_open_max_calls

            return True

    def record_success(self) -> None:
        """记录一次成功调用，根据状态决定是否闭合熔断器。"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"[CircuitBreaker:{self.name}] 试探成功，熔断器闭合")
            else:
                # CLOSED 状态下成功则清空失败计数
                self._failure_count = 0

    def record_failure(self) -> None:
        """记录一次失败调用，根据状态决定是否打开熔断器。"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"[CircuitBreaker:{self.name}] 半开试探失败，重新熔断，失败计数={self._failure_count}"
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"[CircuitBreaker:{self.name}] 连续失败 {self._failure_count} 次，熔断器打开"
                )

    def call(self, func, *args, **kwargs):
        """
        包装一次远程调用，自动记录成功/失败并切换状态。
        注意：该方法不适用于流式响应；流式响应请手动调用 can_call / record_success / record_failure。
        """
        if not self.can_call():
            raise CircuitBreakerOpen(f"熔断器已打开（{self.name}），拒绝远程调用")

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exception:
            self.record_failure()
            raise


class CircuitBreakerOpen(Exception):
    """熔断器打开时抛出的异常。"""
    pass


# ============================================================
# 全局熔断器实例（由 views.py 在启动时构造）
# ============================================================
_default_cb: Optional[CircuitBreaker] = None
_default_cb_lock = threading.Lock()


def get_orchestration_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    half_open_max_calls: int = 1,
) -> CircuitBreaker:
    """
    获取 AI 编排服务全局熔断器（单例）。
    """
    global _default_cb
    if _default_cb is None:
        with _default_cb_lock:
            if _default_cb is None:
                _default_cb = CircuitBreaker(
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    half_open_max_calls=half_open_max_calls,
                    name="ai_orchestrator",
                )
    return _default_cb
