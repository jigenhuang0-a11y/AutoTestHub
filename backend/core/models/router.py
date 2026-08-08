"""
LLM Router — 按任务类型智能路由到最优模型

核心设计:
- 根据 task_type 自动选择模型
- 支持 Provider 降级（A 挂了用 B）
- 内置重试 + 超时保护
"""
import logging
from typing import Optional, Generator

from core.llm_provider import BaseLLMProvider
from core.models.provider_pool import get_provider_pool
from core.config import LLMRouterConfig, get_available_providers, MODEL_REGISTRY

logger = logging.getLogger(__name__)


class LLMRouter:
    """
    智能模型路由器
    
    用法:
        router = LLMRouter()
        
        # 自动选择模型
        answer = router.chat(
            task_type="code_generation",
            messages=[{"role": "user", "content": "写一个Python排序函数"}]
        )
        
        # 指定模型
        answer = router.chat(
            model="deepseek-chat",
            messages=[...]
        )
    """
    
    def __init__(self, config: Optional[LLMRouterConfig] = None, user_id: int = None):
        self.config = config or LLMRouterConfig()
        self._pool = get_provider_pool()
        self.user_id = user_id
    
    def chat(
        self,
        messages: list,
        task_type: str = "fast_chat",
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        智能路由对话
        
        Args:
            messages: OpenAI 格式消息列表
            task_type: 任务类型 (planning / code_generation / ...)
            model: 指定模型（不指定则自动路由）
            temperature: 覆盖默认温度
            max_tokens: 覆盖默认 token 数
        """
        provider, used_model = self._resolve_provider(
            task_type=task_type,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        logger.info(f"[LLMRouter] {task_type} → {used_model} ({provider.__class__.__name__})")
        
        try:
            return provider.chat(messages)
        except Exception as e:
            logger.error(f"[LLMRouter] {used_model} 调用失败: {e}")
            # 降级到 fallback
            fallback = self._pool.get('dashscope', model='qwen-turbo')
            logger.warning(f"[LLMRouter] 降级到 {fallback.model}")
            return fallback.chat(messages)
    
    def chat_stream(
        self,
        messages: list,
        task_type: str = "fast_chat",
        model: Optional[str] = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """流式对话（用于 SSE 推送）"""
        provider, used_model = self._resolve_provider(task_type=task_type, model=model, **kwargs)
        logger.info(f"[LLMRouter] stream {task_type} → {used_model}")
        
        try:
            yield from provider.chat_stream(messages)
        except Exception as e:
            logger.error(f"[LLMRouter] stream {used_model} 失败: {e}")
            fallback = self._pool.get('dashscope', model='qwen-turbo')
            logger.warning(f"[LLMRouter] 降级到 {fallback.model}")
            yield from fallback.chat_stream(messages)
    
    def embed(self, text: str) -> list:
        """文本向量化（固定走千问 embedding）"""
        provider = self._pool.get('dashscope', model='text-embedding-v3')
        return provider.embed(text)
    
    def get_available_models(self) -> list[dict]:
        """列出所有可用模型"""
        available_providers = get_available_providers()
        models = []
        for name, config in MODEL_REGISTRY.items():
            if config.provider in available_providers:
                models.append({
                    "name": name,
                    "provider": config.provider,
                    "capabilities": config.capabilities,
                    "priority": config.priority,
                })
        return sorted(models, key=lambda m: m['priority'], reverse=True)
    
    def _resolve_provider(
        self,
        task_type: str,
        model: Optional[str] = None,
        **kwargs,
    ) -> tuple[BaseLLMProvider, str]:
        """解析最终的 Provider 和模型"""
        available = get_available_providers()
        
        if model:
            # 用户指定了模型
            return self._pool.get_for_model(model, **kwargs), model
        
        # 自动路由
        model_name = self.config.get_model(task_type, available)
        return self._pool.get_for_model(model_name, **kwargs), model_name

    def execute(self, action: str = None, **kwargs) -> dict:
        """MCP 统一入口（system_health）"""
        if action == "system_health":
            try:
                models = self.get_available_models()
                return {
                    "status": "healthy",
                    "available_models_count": len(models),
                    "available_models": [m["name"] for m in models],
                }
            except Exception as e:
                logger.error(f"[LLMRouter.execute] 健康检查失败: {e}")
                return {"status": "unhealthy", "error": str(e)}
        return {"error": f"unknown action: {action}"}


# ============================================================
# 全局单例
# ============================================================
_router_instance: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    """获取全局 LLMRouter 单例"""
    global _router_instance
    if _router_instance is None:
        _router_instance = LLMRouter()
    return _router_instance
