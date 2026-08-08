"""
Provider 实例池 — 连接复用，懒加载（去 Django 依赖版）
"""
import logging
import threading
from typing import Optional

from app.core.llm_provider import BaseLLMProvider, DashScopeProvider, DeepSeekProvider, GLMProvider
from app.core.config import get_available_providers

logger = logging.getLogger(__name__)


class ProviderPool:

    _PROVIDER_CLASSES = {
        "dashscope": DashScopeProvider,
        "deepseek": DeepSeekProvider,
        "glm": GLMProvider,
    }

    def __init__(self):
        self._lock = threading.Lock()
        self._instances: dict[str, BaseLLMProvider] = {}

    def get(self, provider_name: str, **kwargs) -> BaseLLMProvider:
        name = provider_name.lower()
        if name not in self._PROVIDER_CLASSES:
            raise ValueError(f"不支持的 Provider: {name}")

        available = get_available_providers()
        if name not in available:
            raise ValueError(f"Provider '{name}' 未配置 API Key")

        cache_key = self._make_key(name, kwargs)
        with self._lock:
            if cache_key not in self._instances:
                provider_cls = self._PROVIDER_CLASSES[name]
                self._instances[cache_key] = provider_cls(**kwargs)
                logger.info(f"[ProviderPool] 创建新实例: {cache_key}")
            return self._instances[cache_key]

    def get_default(self) -> BaseLLMProvider:
        available = get_available_providers()
        if "dashscope" in available:
            return self.get("dashscope", model="qwen-plus")
        if "deepseek" in available:
            return self.get("deepseek", model="deepseek-chat")
        if "glm" in available:
            return self.get("glm", model="glm-4-flash")
        raise ValueError("没有可用的 LLM Provider，请至少配置一个 API Key")

    def get_for_model(self, model_name: str, **kwargs) -> BaseLLMProvider:
        from app.core.config import MODEL_REGISTRY, _get_provider_name
        provider_name = _get_provider_name(model_name)
        if model_name in MODEL_REGISTRY:
            config = MODEL_REGISTRY[model_name]
            final_kwargs = {
                "model": model_name,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
            }
            final_kwargs.update(kwargs)
        else:
            final_kwargs = {"model": model_name, **kwargs}
        return self.get(provider_name, **final_kwargs)

    def list_available(self) -> list[str]:
        return sorted(get_available_providers())

    @staticmethod
    def _make_key(provider: str, kwargs: dict) -> str:
        model = kwargs.get("model", "default")
        temp = kwargs.get("temperature", 0.7)
        return f"{provider}:{model}:t{temp}"


_pool_instance: Optional[ProviderPool] = None
_pool_lock = threading.Lock()


def get_provider_pool() -> ProviderPool:
    global _pool_instance
    if _pool_instance is None:
        with _pool_lock:
            if _pool_instance is None:
                _pool_instance = ProviderPool()
    return _pool_instance
