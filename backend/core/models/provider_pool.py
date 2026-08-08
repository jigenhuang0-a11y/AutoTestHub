"""
Provider 实例池 — 连接复用，懒加载

与现有 llm_provider.py 的关系：
- llm_provider.py 是底层 HTTP 封装（单次创建单次使用）
- provider_pool.py 是上层池化管理（复用实例，按需创建）
- 两者共存，不互相替代
"""
import logging
import threading
from typing import Optional

from core.llm_provider import (
    BaseLLMProvider,
    DashScopeProvider,
    DeepSeekProvider,
    GLMProvider,
)
from core.config import get_available_providers

logger = logging.getLogger(__name__)


class ProviderPool:
    """
    Provider 实例池 — 线程安全，懒加载
    
    用法:
        pool = ProviderPool()
        llm = pool.get('deepseek', model='deepseek-chat')
        answer = llm.chat([{"role": "user", "content": "你好"}])
    """
    
    # Provider 名称 → 构造函数映射
    _PROVIDER_CLASSES = {
        'dashscope': DashScopeProvider,
        'deepseek': DeepSeekProvider,
        'glm': GLMProvider,
    }
    
    def __init__(self):
        self._lock = threading.Lock()
        self._instances: dict[str, BaseLLMProvider] = {}
    
    def get(self, provider_name: str, **kwargs) -> BaseLLMProvider:
        """
        获取或创建 Provider 实例
        
        Args:
            provider_name: 'dashscope' | 'deepseek' | 'glm'
            **kwargs: model, temperature, max_tokens 等
        
        Returns:
            BaseLLMProvider 实例
        
        Raises:
            ValueError: Provider 不可用或未配置 API Key
        """
        name = provider_name.lower()
        
        if name not in self._PROVIDER_CLASSES:
            raise ValueError(f"不支持的 Provider: {name}")
        
        # 检查 API Key 是否配置
        available = get_available_providers()
        if name not in available:
            raise ValueError(
                f"Provider '{name}' 未配置 API Key，请在 .env 中设置对应环境变量"
            )
        
        # 生成缓存 key：provider_name + 关键参数
        cache_key = self._make_key(name, kwargs)
        
        with self._lock:
            if cache_key not in self._instances:
                provider_cls = self._PROVIDER_CLASSES[name]
                self._instances[cache_key] = provider_cls(**kwargs)
                logger.info(f"[ProviderPool] 创建新实例: {cache_key}")
            
            return self._instances[cache_key]
    
    def get_default(self) -> BaseLLMProvider:
        """获取默认 Provider（第一个可用的）"""
        available = get_available_providers()
        if 'dashscope' in available:
            return self.get('dashscope', model='qwen-plus')
        if 'deepseek' in available:
            return self.get('deepseek', model='deepseek-chat')
        if 'glm' in available:
            return self.get('glm', model='glm-4-flash')
        raise ValueError("没有可用的 LLM Provider，请至少配置一个 API Key")
    
    def get_for_model(self, model_name: str, **kwargs) -> BaseLLMProvider:
        """根据模型名自动选择 Provider"""
        from core.config import MODEL_REGISTRY, _get_provider_name
        provider_name = _get_provider_name(model_name)
        if model_name in MODEL_REGISTRY:
            config = MODEL_REGISTRY[model_name]
            final_kwargs = {
                'model': model_name,
                'temperature': config.temperature,
                'max_tokens': config.max_tokens,
            }
            final_kwargs.update(kwargs)
        else:
            final_kwargs = {'model': model_name, **kwargs}
        return self.get(provider_name, **final_kwargs)
    
    def list_available(self) -> list[str]:
        """列出所有已配置的 Provider"""
        return sorted(get_available_providers())
    
    def __len__(self):
        with self._lock:
            return len(self._instances)
    
    def __repr__(self):
        available = self.list_available()
        return f"<ProviderPool available={available} cached={len(self)}>"
    
    @staticmethod
    def _make_key(provider: str, kwargs: dict) -> str:
        """生成缓存 key"""
        model = kwargs.get('model', 'default')
        temp = kwargs.get('temperature', 0.7)
        return f"{provider}:{model}:t{temp}"


# 全局单例
_pool_instance: Optional[ProviderPool] = None
_pool_lock = threading.Lock()


def get_provider_pool() -> ProviderPool:
    """获取全局 ProviderPool 单例"""
    global _pool_instance
    if _pool_instance is None:
        with _pool_lock:
            if _pool_instance is None:
                _pool_instance = ProviderPool()
    return _pool_instance
