"""
健壮性保障层：统一重试、降级、熔断、幂等

覆盖场景：
- 工具调用临时失败 → 退避重试
- LLM 调用临时失败 → 降级模型或回退策略
- 下游服务不可用 → 熔断后短路
- 结果重复提交 → 幂等跳过
"""

import time
import random
import functools
import logging
from typing import TypeVar, Callable, Any, Optional, Tuple

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ============================================================
# 配置常量
# ============================================================

# 工具调用重试
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0          # 秒
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_JITTER = True

# LLM 重试
LLM_MAX_RETRIES = 2
LLM_BASE_DELAY = 2.0

# 熔断器
CIRCUIT_BREAKER_THRESHOLD = 5     # 连续失败 N 次后熔断
CIRCUIT_BREAKER_TIMEOUT = 30      # 熔断后 N 秒尝试半开
CIRCUIT_HALF_OPEN_LIMIT = 1       # 半开状态下允许的探测请求数

# 可重试的 HTTP 状态码
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}

# ============================================================
# 工具调用重试（指数退避 + 抖动）
# ============================================================

class RetryExhausted(Exception):
    """重试次数耗尽"""
    def __init__(self, original_exception: Exception, attempts: int):
        self.original_exception = original_exception
        self.attempts = attempts
        super().__init__(f"重试 {attempts} 次后仍失败: {original_exception}")


def _is_retryable(exc: Exception) -> bool:
    """判断异常是否可重试"""
    # HTTP 异常
    http_exc = getattr(exc, "response", None) or getattr(exc, "resp", None)
    if http_exc is not None:
        status = getattr(http_exc, "status_code", None) or getattr(http_exc, "status", None)
        if status in RETRYABLE_HTTP_STATUS:
            return True
        if status is not None and status < 500:
            return False

    # 网络异常
    exc_name = type(exc).__name__
    if exc_name in ("ConnectionError", "Timeout", "ReadTimeout",
                    "ConnectTimeout", "ConnectionTimeout", "SSLError",
                    "RemoteDisconnected", "ChunkedEncodingError"):
        return True
    if "timeout" in str(exc).lower() or "connection" in str(exc).lower():
        return True

    # ValueError / TypeError（可重试 — 可能是临时数据问题）
    # 默认不可重试，防止死循环
    return False


def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    jitter: bool = DEFAULT_JITTER,
    retryable_check: Callable[[Exception], bool] = _is_retryable,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
):
    """
    异步/同步通用重试装饰器。

    重试策略：
    1. 指数退避：delay = base_delay * (backoff_factor ^ (attempt - 1))
    2. 随机抖动：delay *= (0.5 + random.random())  避免雷鸣羊群
    3. 仅对可重试错误生效（5xx、超时、连接错误）

    Args:
        max_retries: 最大重试次数（不含首次调用）
        base_delay: 基础延迟（秒）
        backoff_factor: 退避倍数
        jitter: 是否启用随机抖动
        retryable_check: 判断异常是否可重试
        on_retry: 重试回调 (exception, attempt, delay)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt >= max_retries:
                        raise RetryExhausted(e, attempt) from e
                    if not retryable_check(e):
                        raise

                    delay = base_delay * (backoff_factor ** attempt)
                    if jitter:
                        delay *= (0.5 + random.random())

                    logger.warning(
                        f"[Retry] {func.__name__} 失败 (attempt {attempt+1}/{max_retries+1}), "
                        f"{delay:.1f}s 后重试: {e}"
                    )

                    if on_retry:
                        try:
                            on_retry(e, attempt + 1, delay)
                        except Exception:
                            pass

                    time.sleep(delay)
            raise last_exc  # 理论上不会走到这里

        return wrapper
    return decorator


# ============================================================
# 降级策略
# ============================================================

class DegradationHandler:
    """
    降级处理器：当主策略失败时，按优先级尝试备用方案。

    用法：
        handler = DegradationHandler()
        handler.add_fallback(lambda: call_primary("a"))
        handler.add_fallback(lambda: call_secondary("b"))
        result = handler.execute()
    """

    def __init__(self, name: str = "degradation"):
        self.name = name
        self._fallbacks: list[Callable[[], Any]] = []

    def add_fallback(self, fn: Callable[[], Any], description: str = ""):
        """按优先级从高到低添加回退方案"""
        self._fallbacks.append((fn, description))

    def execute(self) -> Any:
        """顺序尝试所有回退方案，全部失败则抛出最后一次异常"""
        errors = []
        for i, (fn, desc) in enumerate(self._fallbacks):
            label = desc or f"fallback_{i}"
            try:
                logger.info(f"[Degradation:{self.name}] 尝试 {label}...")
                return fn()
            except Exception as e:
                logger.warning(f"[Degradation:{self.name}] {label} 失败: {e}")
                errors.append(e)
        raise Exception(f"[Degradation:{self.name}] 所有 {len(self._fallbacks)} 个回退方案均失败: {errors}")


# ============================================================
# 熔断器
# ============================================================

class CircuitBreaker:
    """
    简单熔断器（CLOSED → OPEN → HALF_OPEN → CLOSED）

    状态机：
    ┌─────────┐   连续失败 >= threshold   ┌──────────┐
    │ CLOSED  │ ─────────────────────────► │  OPEN    │
    │ (正常)  │                            │ (熔断)   │
    └────┬────┘                            └────┬─────┘
         │ 成功重置                             │ timeout 后
         │                                      ▼
         │                               ┌─────────────┐
         │         探测成功              │ HALF_OPEN   │
         └──────────────────────────────│ (探测中)    │
                探测失败 → 重新 OPEN    └─────────────┘
    """

    def __init__(self, name: str, threshold: int = CIRCUIT_BREAKER_THRESHOLD,
                 timeout: float = CIRCUIT_BREAKER_TIMEOUT,
                 half_open_limit: int = CIRCUIT_HALF_OPEN_LIMIT):
        self.name = name
        self.threshold = threshold
        self.timeout = timeout
        self.half_open_limit = half_open_limit
        self._failures = 0
        self._last_failure_time = 0.0
        self._state = "CLOSED"
        self._half_open_attempts = 0

    @property
    def is_open(self) -> bool:
        if self._state == "CLOSED":
            return False
        if self._state == "OPEN":
            if time.time() - self._last_failure_time >= self.timeout:
                self._state = "HALF_OPEN"
                self._half_open_attempts = 0
                logger.info(f"[CircuitBreaker:{self.name}] OPEN → HALF_OPEN")
                return False
            return True
        if self._state == "HALF_OPEN":
            if self._half_open_attempts >= self.half_open_limit:
                return True
        return False

    def record_success(self):
        if self._state == "HALF_OPEN":
            self._state = "CLOSED"
            self._failures = 0
            logger.info(f"[CircuitBreaker:{self.name}] HALF_OPEN → CLOSED")
        elif self._state == "CLOSED":
            self._failures = 0

    def record_failure(self):
        self._failures += 1
        self._last_failure_time = time.time()
        if self._state == "CLOSED" and self._failures >= self.threshold:
            self._state = "OPEN"
            logger.warning(
                f"[CircuitBreaker:{self.name}] CLOSED → OPEN "
                f"(连续 {self._failures} 次失败)"
            )
        elif self._state == "HALF_OPEN":
            self._state = "OPEN"
            logger.warning(
                f"[CircuitBreaker:{self.name}] HALF_OPEN → OPEN "
                f"(探测失败)"
            )
        self._half_open_attempts += 1

    def __repr__(self):
        return f"<CircuitBreaker:{self.name} state={self._state} failures={self._failures}>"


# 全局熔断器实例（按服务名隔离）
_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """获取或创建指定服务的熔断器"""
    if service_name not in _breakers:
        _breakers[service_name] = CircuitBreaker(name=service_name)
    return _breakers[service_name]


# ============================================================
# 幂等性工具
# ============================================================

class IdempotencyTracker:
    """
    幂等追踪器：防止同一 task + step 被重复处理。

    基于内存集合，生产环境建议替换为 Redis（60s TTL）。
    """

    def __init__(self, max_size: int = 10000):
        self._processed: set[str] = {}
        self._max_size = max_size

    def make_key(self, task_id: str, step_index: int, agent: str) -> str:
        return f"{task_id}:{step_index}:{agent}"

    def is_processed(self, task_id: str, step_index: int, agent: str) -> bool:
        return self.make_key(task_id, step_index, agent) in self._processed

    def mark_processed(self, task_id: str, step_index: int, agent: str):
        key = self.make_key(task_id, step_index, agent)
        self._processed[key] = True
        # 防止内存泄漏：超过上限时清空一半
        if len(self._processed) > self._max_size:
            keys = list(self._processed.keys())
            for k in keys[:self._max_size // 2]:
                del self._processed[k]
            logger.info(f"[Idempotency] 清理 {self._max_size // 2} 个过期幂等记录")

    def unmark(self, task_id: str, step_index: int, agent: str):
        """失败后取消标记，允许重试"""
        self._processed.pop(self.make_key(task_id, step_index, agent), None)


# 全局幂等追踪器
_idempotency_tracker = IdempotencyTracker()


def get_idempotency_tracker() -> IdempotencyTracker:
    return _idempotency_tracker


# ============================================================
# 便捷函数：包装工具调用
# ============================================================

def call_with_robustness(
    func: Callable[..., T],
    *args,
    circuit_name: str = "default",
    max_retries: int = DEFAULT_MAX_RETRIES,
    fallback: Optional[Callable[[], T]] = None,
    **kwargs,
) -> T:
    """
    一站式健壮性调用：熔断 → 重试 → 降级

    Args:
        func: 实际调用函数
        circuit_name: 熔断器名称（按服务隔离）
        max_retries: 最大重试次数
        fallback: 降级回调（全部失败时执行）

    Returns:
        调用结果
    """
    breaker = get_circuit_breaker(circuit_name)

    if breaker.is_open:
        if fallback:
            logger.warning(f"[Robustness] {circuit_name} 已熔断，使用降级方案")
            return fallback()
        raise Exception(f"[Robustness] {circuit_name} 已熔断，无降级方案")

    @retry_with_backoff(max_retries=max_retries)
    def _wrapped():
        return func(*args, **kwargs)

    try:
        result = _wrapped()
        breaker.record_success()
        return result
    except Exception as e:
        breaker.record_failure()
        if fallback:
            logger.warning(f"[Robustness] {circuit_name} 调用失败，使用降级方案: {e}")
            return fallback()
        raise


# ============================================================
# LLM 专用重试 + 降级
# ============================================================

def call_llm_with_fallback(
    router,
    messages: list,
    task_type: str = "default",
    fallback_model: str = None,
    team_id: str = None,
) -> str:
    """
    LLM 调用包装：主模型失败 → 自动降级到备用模型。

    Args:
        router: LLMRouter 实例
        messages: 对话消息列表
        task_type: 任务类型（planning / evaluation / data_generation）
        fallback_model: 降级模型名（默认 None，不启用降级）
        team_id: 团队 ID（SaaS：用于查询团队模型偏好）

    Returns:
        LLM 响应文本
    """
    handler = DegradationHandler(name=f"llm:{task_type}")

    # 主策略：使用路由器自动选择模型（含团队偏好）
    def call_primary():
        return router.chat(messages, task_type=task_type, team_id=team_id)

    handler.add_fallback(call_primary, description=f"primary:{task_type}")

    # 降级策略：使用指定的备用模型
    if fallback_model:
        def call_fallback():
            return router.chat(messages, model=fallback_model, team_id=team_id)
        handler.add_fallback(call_fallback, description=f"fallback:{fallback_model}")

    return handler.execute()
