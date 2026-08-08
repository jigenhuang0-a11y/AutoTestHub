"""
LLM Router — 按任务类型智能路由到最优模型（去 Django 依赖版）
"""
import logging
from typing import Optional, Generator

from app.core.llm_provider import BaseLLMProvider
from app.core.provider_pool import get_provider_pool
from app.core.config import LLMRouterConfig, get_available_providers, MODEL_REGISTRY
from app.core.task_store import get_task_store

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
    ) -> str:
        provider, used_model = self._resolve_provider(
            task_type=task_type, model=model, temperature=temperature,
            max_tokens=max_tokens, team_id=team_id,
        )
        logger.info(f"[LLMRouter] {task_type} -> {used_model}")
        try:
            return provider.chat(messages)
        except Exception as e:
            logger.error(f"[LLMRouter] {used_model} 失败: {e}")
            fallback = self._pool.get("dashscope", model="qwen-turbo")
            logger.warning(f"[LLMRouter] 降级到 {fallback.model}")
            return fallback.chat(messages)

    def chat_stream(
        self,
        messages: list,
        task_type: str = "fast_chat",
        model: Optional[str] = None,
        team_id: Optional[str] = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        provider, used_model = self._resolve_provider(
            task_type=task_type, model=model, team_id=team_id, **kwargs
        )
        logger.info(f"[LLMRouter] stream {task_type} -> {used_model}")
        try:
            yield from provider.chat_stream(messages)
        except Exception as e:
            logger.error(f"[LLMRouter] stream {used_model} 失败: {e}")
            fallback = self._pool.get("dashscope", model="qwen-turbo")
            yield from fallback.chat_stream(messages)

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

        try:
            return provider.chat_raw(messages, **kwargs)
        except Exception as e:
            logger.error(f"[LLMRouter] {used_model} chat_with_tools 失败: {e}")
            # 降级：纯文本 chat（不带工具）
            fallback = self._pool.get("dashscope", model="qwen-turbo")
            logger.warning(f"[LLMRouter] 降级到纯文本 {fallback.model}")
            try:
                content = fallback.chat(messages)
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


_router_instance: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = LLMRouter()
    return _router_instance
