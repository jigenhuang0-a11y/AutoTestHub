"""L1 模型底座 - 统一模型网关。

对外唯一入口：chat() / embedding()。
职责（红线 #1 的物理载体）：
- 路由：按 model 名选择适配器（DeepSeek 主力，通义备用可降级）
- 护栏：调用前做 Prompt 注入检测，调用后做输出合规
- 配额：按 tenant_id 限流（QPS）+ 熔断（连续失败）
- 埋点：全量记录 CallLog（异步写库，P1 先写内存/日志，P2 落 MySQL）

限流/熔断 P1 用内存版（单机演示足够）；P2 换 Redis 分布式。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

from harness_core.config import settings
from harness_core.llm.adapter import DeepSeekAdapter, QwenAdapter
from harness_core.llm.base import (
    ChatMessage,
    ChatResponse,
    ModelAdapter,
)
from harness_core.llm.guard import Guardrail
from harness_core.logging import logger

# 模型名 -> 适配器工厂
_ADAPTER_FACTORIES: dict[str, type[ModelAdapter]] = {
    "deepseek-chat": DeepSeekAdapter,
    "qwen-plus": QwenAdapter,
}

# 降级顺序（主力失败切备用）
_FALLBACK_ORDER: dict[str, list[str]] = {
    "deepseek-chat": ["deepseek-chat", "qwen-plus"],
    "qwen-plus": ["qwen-plus"],
}


@dataclass
class GatewayContext:
    tenant_id: int
    agent_id: Optional[int] = None
    trace_id: Optional[str] = None
    model_preference: str = "deepseek-chat"


class _RateLimiter:
    """单机令牌桶限流（P1 内存版）。"""

    def __init__(self, qps: int) -> None:
        self.qps = qps
        self._lock = asyncio.Lock()
        self._tokens = qps
        self._last = time.monotonic()

    async def acquire(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self.qps, self._tokens + elapsed * self.qps)
            self._last = now
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False


class _CircuitBreaker:
    """连续失败熔断。"""

    def __init__(self, failures: int, reset_seconds: int) -> None:
        self.failures = failures
        self.reset_seconds = reset_seconds
        self._count = 0
        self._opened_at: float | None = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if time.monotonic() - self._opened_at >= self.reset_seconds:
            self._opened_at = None
            self._count = 0
            return True
        return False

    def on_success(self) -> None:
        self._count = 0

    def on_failure(self) -> None:
        self._count += 1
        if self._count >= self.failures:
            self._opened_at = time.monotonic()


class ModelGateway:
    def __init__(self) -> None:
        self._adapters: dict[str, ModelAdapter] = {}
        self.guard = Guardrail(
            prompt_injection_check=settings.guardrail_prompt_injection_check,
            output_moderation=settings.guardrail_output_moderation,
        )
        self._limiters: dict[int, _RateLimiter] = {}
        self._breakers: dict[str, _CircuitBreaker] = {}

    def _get_adapter(self, model: str) -> ModelAdapter:
        if model not in self._adapters:
            factory = _ADAPTER_FACTORIES.get(model)
            if not factory:
                raise ValueError(f"未知模型: {model}")
            self._adapters[model] = factory()
        return self._adapters[model]

    def _limiter(self, tenant_id: int) -> _RateLimiter:
        if tenant_id not in self._limiters:
            self._limiters[tenant_id] = _RateLimiter(settings.default_qps_limit)
        return self._limiters[tenant_id]

    def _breaker(self, model: str) -> _CircuitBreaker:
        if model not in self._breakers:
            self._breakers[model] = _CircuitBreaker(
                settings.circuit_breaker_failures,
                settings.circuit_breaker_reset_seconds,
            )
        return self._breakers[model]

    async def chat(
        self, ctx: GatewayContext, messages: list[ChatMessage], **kwargs
    ) -> ChatResponse:
        # 1. 护栏：Prompt 注入检测
        for m in messages:
            gr = self.guard.check_prompt(m.content)
            if not gr.passed:
                logger.warning(f"[护栏] 拦截 Prompt 注入 tenant={ctx.tenant_id}: {gr.reason}")
                return ChatResponse(
                    content="",
                    model=ctx.model_preference,
                    raw={"guard_blocked": gr.reason},
                )

        # 2. 限流
        limiter = self._limiter(ctx.tenant_id)
        if not await limiter.acquire():
            raise RuntimeError("QPS 限流触发")

        # 3. 路由 + 降级
        tried = _FALLBACK_ORDER.get(ctx.model_preference, [ctx.model_preference])
        last_err: Exception | None = None
        for model in tried:
            breaker = self._breaker(model)
            if not breaker.allow():
                logger.warning(f"[熔断] {model} 处于打开状态，跳过")
                continue
            try:
                adapter = self._get_adapter(model)
                resp = await adapter.chat(messages, **kwargs)
                # 4. 护栏：输出合规
                og = self.guard.check_output(resp.content)
                if not og.passed:
                    logger.warning(f"[护栏] 输出合规拦截: {og.reason}")
                    resp.content = "【输出已被安全护栏拦截】"
                breaker.on_success()
                self._emit_log(ctx, resp, kind="llm")
                return resp
            except Exception as e:  # noqa: BLE001
                breaker.on_failure()
                last_err = e
                logger.error(f"[网关] {model} 调用失败: {e}")

        raise RuntimeError(f"所有模型均不可用: {last_err}")

    async def stream_chat(
        self, ctx: GatewayContext, messages: list[ChatMessage], **kwargs
    ):
        """流式 chat（SSE 前置）。当前复用适配器流式接口；无流式的模型退化为整段返回。"""
        for m in messages:
            gr = self.guard.check_prompt(m.content)
            if not gr.passed:
                logger.warning(f"[护栏] 拦截 Prompt 注入(流): {gr.reason}")
                return
        limiter = self._limiter(ctx.tenant_id)
        if not await limiter.acquire():
            raise RuntimeError("QPS 限流触发")
        tried = _FALLBACK_ORDER.get(ctx.model_preference, [ctx.model_preference])
        last_err: Exception | None = None
        for model in tried:
            breaker = self._breaker(model)
            if not breaker.allow():
                continue
            try:
                adapter = self._get_adapter(model)
                total = 0
                async for chunk in adapter.stream_chat(messages, **kwargs):
                    og = self.guard.check_output(chunk)
                    if not og.passed:
                        yield "【输出已被安全护栏拦截】"
                        return
                    total += len(chunk)
                    yield chunk
                breaker.on_success()
                self._emit_log(ctx, ChatResponse(content="", model=model, completion_tokens=total), kind="llm-stream")
                return
            except Exception as e:  # noqa: BLE001
                breaker.on_failure()
                last_err = e
                logger.error(f"[网关] {model} 流式失败: {e}")
        raise RuntimeError(f"所有模型均不可用: {last_err}")

    def _emit_log(self, ctx: GatewayContext, resp: ChatResponse, kind: str) -> None:
        """埋点：P3 接入指标收集器 + 日志。"""
        from harness_core.metrics.collector import metrics

        metrics.record_call(
            model=resp.model,
            in_tokens=resp.prompt_tokens,
            out_tokens=resp.completion_tokens,
            error=bool(resp.raw.get("guard_blocked")),
        )
        if ctx.trace_id:
            metrics.record_trace(ctx.trace_id, kind, ok=not resp.raw.get("guard_blocked"))
        logger.info(
            f"[埋点] kind={kind} tenant={ctx.tenant_id} agent={ctx.agent_id} "
            f"model={resp.model} in={resp.prompt_tokens} out={resp.completion_tokens} "
            f"trace={ctx.trace_id}"
        )


# 全局单例
gateway = ModelGateway()
