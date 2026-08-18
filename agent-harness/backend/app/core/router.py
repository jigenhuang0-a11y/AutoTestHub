"""
LLM Router — 按任务类型智能路由到最优模型（去 Django 依赖版）
"""
import logging
import time
from typing import Optional, Generator, List

from app.core.llm_provider import BaseLLMProvider
from app.core.provider_pool import get_provider_pool
from app.core.config import LLMRouterConfig, get_available_providers, MODEL_REGISTRY
from app.core.task_store import get_task_store
from app.core.eval_event_store import is_tracked_feature, build_event, get_eval_event_store

logger = logging.getLogger(__name__)


class LLMRouter:

    def __init__(self, config: Optional[LLMRouterConfig] = None):
        self.config = config or LLMRouterConfig()
        self._pool = get_provider_pool()

    def chat(
        self,
        messages: list,
        task_type: str = "fast_chat",
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        team_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **extra_kwargs,
    ) -> str:
        provider, used_model = self._resolve_provider(
            task_type=task_type, model=model, temperature=temperature,
            max_tokens=max_tokens, team_id=team_id,
        )
        logger.info(f"[LLMRouter] {task_type} -> {used_model}")
        trace_kwargs = {
            "__langfuse_name": f"{task_type}",
            "__langfuse_session_id": session_id,
            "__langfuse_user_id": user_id,
            "__langfuse_meta": {"feature": task_type, "model": used_model},
        }
        start = time.time()
        try:
            content = provider.chat(messages, **trace_kwargs, **extra_kwargs)
            latency_ms = int((time.time() - start) * 1000)
            self._record_event(task_type, used_model, provider, messages, content, latency_ms)
            return content
        except Exception as e:
            logger.error(f"[LLMRouter] {used_model} 失败: {e}")
            fallback_model = self.config.route_map.get("fallback", ["deepseek-chat"])[0]
            fallback = self._pool.get_for_model(fallback_model)
            logger.warning(f"[LLMRouter] 降级到 {fallback.model}")
            content = fallback.chat(messages, **trace_kwargs, **extra_kwargs)
            latency_ms = int((time.time() - start) * 1000)
            self._record_event(task_type, fallback.model, fallback, messages, content, latency_ms)
            return content

    def chat_stream(
        self,
        messages: list,
        task_type: str = "fast_chat",
        model: Optional[str] = None,
        team_id: Optional[str] = None,
        enable_reasoning: bool = False,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> Generator[dict, None, None]:
        """
        流式对话，返回事件字典（与 BaseLLMProvider.chat_stream 契约一致）：
          {"type": "delta", "content": str}
          {"type": "reasoning", "content": str}
          {"type": "done", "content": str}
          {"type": "error", "message": str}
        """
        # 深度思考模式：优先走原生推理模型（DeepSeek Reasoner），
        # 并把任务类型改为 reasoning，避免被路由到不具备 reasoning 能力的模型。
        if enable_reasoning:
            task_type = "reasoning"
        provider, used_model = self._resolve_provider(
            task_type=task_type, model=model, team_id=team_id, **kwargs
        )
        logger.info(f"[LLMRouter] stream {task_type} -> {used_model} (reasoning={enable_reasoning})")
        trace_kwargs = {
            "__langfuse_name": f"{task_type}_stream",
            "__langfuse_session_id": session_id,
            "__langfuse_user_id": user_id,
            "__langfuse_meta": {"feature": task_type, "model": used_model, "stream": True},
        }
        start = time.time()
        try:
            yield from self._stream_with_event(
                provider.chat_stream(messages, enable_reasoning=enable_reasoning, **trace_kwargs, **kwargs),
                task_type, used_model, provider, messages,
            )
        except Exception as e:
            logger.error(f"[LLMRouter] stream {used_model} 失败: {e}")
            fallback_model = self.config.route_map.get("fallback", ["deepseek-chat"])[0]
            fallback = self._pool.get_for_model(fallback_model)
            yield from self._stream_with_event(
                fallback.chat_stream(messages, enable_reasoning=enable_reasoning, **trace_kwargs, **kwargs),
                task_type, fallback.model, fallback, messages,
            )

    def chat_with_tools(
        self,
        messages: list,
        tools: list[dict],
        task_type: str = "agent",
        model: Optional[str] = None,
        temperature: float = 0.3,
        team_id: Optional[str] = None,
    ) -> dict:
        """
        ReAct / Agent 专用：带工具调用的 LLM 请求。

        Args:
            messages: 对话消息列表
            tools: OpenAI Function Calling 格式的工具列表
            task_type: 任务类型（默认 agent）
            model: 强制指定模型（可选）
            temperature: 温度参数

        Returns:
            {
                "content": str | None,
                "tool_calls": [{"id":..., "function": {"name":..., "arguments":...}}] | None,
                "model": str,
                "usage": dict,
            }
        """
        provider, used_model = self._resolve_provider(
            task_type=task_type, model=model, temperature=temperature, team_id=team_id,
        )
        logger.info(f"[LLMRouter] chat_with_tools {task_type} -> {used_model}, tools={len(tools)}")

        kwargs = {"temperature": temperature}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        start = time.time()
        try:
            result = provider.chat_raw(messages, **kwargs)
            latency_ms = int((time.time() - start) * 1000)
            content = result.get("content", "")
            usage = result.get("usage") or {}
            token_usage = usage.get("total_tokens", 0) or max(1, len(str(content)) // 4)
            self._record_event(task_type, used_model, provider, messages, content, latency_ms, token_usage=token_usage)
            return result
        except Exception as e:
            logger.error(f"[LLMRouter] {used_model} chat_with_tools 失败: {e}")
            # 降级：纯文本 chat（不带工具）
            fallback_model = self.config.route_map.get("fallback", ["deepseek-chat"])[0]
            fallback = self._pool.get_for_model(fallback_model)
            logger.warning(f"[LLMRouter] 降级到纯文本 {fallback.model}")
            try:
                content = fallback.chat(messages)
                latency_ms = int((time.time() - start) * 1000)
                self._record_event(task_type, fallback.model, fallback, messages, content, latency_ms)
                return {"content": content, "tool_calls": None, "model": fallback.model, "usage": {}}
            except Exception as fe:
                logger.error(f"[LLMRouter] 降级也失败: {fe}")
                raise

    def get_available_models(self) -> list[dict]:
        models = []
        for name, config in MODEL_REGISTRY.items():
            models.append({
                "name": name,
                "provider": config.provider,
                "capabilities": config.capabilities,
                "priority": config.priority,
            })
        return sorted(models, key=lambda m: m["priority"], reverse=True)

    def _resolve_provider(
        self, task_type: str, model: Optional[str] = None, team_id: Optional[str] = None, **kwargs
    ) -> tuple[BaseLLMProvider, str]:
        available = get_available_providers()

        # 1) 显式指定 model → 直接用
        if model:
            return self._pool.get_for_model(model, **kwargs), model

        # 2) SaaS 核心：查团队偏好覆盖全局路由
        if team_id:
            try:
                store = get_task_store()
                prefs = store.get_team_model_prefs(team_id)
                if prefs:
                    team_model = prefs.get_model_for_task_type(task_type)
                    if team_model and team_model.strip():
                        # 团队偏好模型可用 → 使用它
                        if team_model in MODEL_REGISTRY:
                            provider_name = MODEL_REGISTRY[team_model].provider
                            if provider_name in available:
                                logger.info(
                                    f"[LLMRouter] {task_type} → 团队偏好 model={team_model} "
                                    f"(team={team_id})"
                                )
                                return self._pool.get_for_model(team_model, **kwargs), team_model
                        # 模型不可用 → 告警后回退全局路由
                        logger.warning(
                            f"[LLMRouter] 团队 {team_id} 偏好模型 {team_model} 不可用，"
                            f"回退全局路由"
                        )
            except Exception as e:
                logger.warning(f"[LLMRouter] 查询团队偏好失败（team={team_id}）: {e}")

        # 3) 回退：全局路由表
        model_name = self.config.get_model(task_type, available)
        return self._pool.get_for_model(model_name, **kwargs), model_name

    def _record_event(
        self,
        task_type: str,
        used_model: str,
        provider: BaseLLMProvider,
        messages: list,
        content: str,
        latency_ms: int,
        retrieved_docs: Optional[List[dict]] = None,
        token_usage: int = 0,
    ) -> None:
        """把一次 LLM 调用记录到 EvalEventStore，供 EvalCenter 事件驱动刷新。"""
        if not is_tracked_feature(task_type):
            return
        try:
            last_user = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    last_user = m.get("content", "")
                    break
            text = content if isinstance(content, str) else str(content)
            event = build_event(
                feature=task_type,
                task_type=task_type,
                model=used_model,
                provider=provider.__class__.__name__,
                input_text=last_user,
                output_text=text,
                latency_ms=latency_ms,
                token_usage=token_usage or max(1, len(text) // 4),
                retrieved_docs=retrieved_docs or [],
            )
            get_eval_event_store().add(event)
        except Exception as e:
            logger.warning(f"[LLMRouter] 记录事件失败: {e}")

    def _stream_with_event(
        self,
        generator: Generator[dict, None, None],
        task_type: str,
        used_model: str,
        provider: BaseLLMProvider,
        messages: list,
    ) -> Generator[dict, None, None]:
        """包裹流式生成器，收集完整输出并在结束后记录事件。"""
        buffer = []
        start = time.time()
        try:
            for chunk in generator:
                if chunk.get("type") in ("delta", "reasoning"):
                    buffer.append(chunk.get("content", ""))
                yield chunk
        finally:
            latency_ms = int((time.time() - start) * 1000)
            content = "".join(buffer)
            self._record_event(task_type, used_model, provider, messages, content, latency_ms)


_router_instance: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = LLMRouter()
    return _router_instance
