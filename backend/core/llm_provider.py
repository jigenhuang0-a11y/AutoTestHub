"""
统一 LLM Provider 抽象层
支持：DashScope(千问)、DeepSeek、GLM(智谱)、SiliconFlow(硅基流动)
后续可扩展更多模型

用法:
    from core.llm_provider import LLMProviderFactory
    llm = LLMProviderFactory.create('dashscope')  # 或 'deepseek', 'glm'
    answer = llm.chat([{"role": "user", "content": "你好"}])
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Generator, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


# ============================================================
# 基础抽象类
# ============================================================
class BaseLLMProvider(ABC):
    """LLM Provider 抽象基类"""

    def __init__(self, api_key: str, model: str, temperature: float = 0.7, max_tokens: int = 2000):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @property
    def supports_vision(self) -> bool:
        """当前模型是否支持图片输入（多模态）"""
        return False

    @abstractmethod
    def chat(self, messages: list, **kwargs) -> str:
        """同步对话，返回完整回答"""
        ...

    @abstractmethod
    def chat_stream(self, messages: list, **kwargs) -> Generator[str, None, None]:
        """流式对话，逐token返回"""
        ...

    def embed(self, text: str) -> list:
        """文本向量化（默认抛异常，需子类覆盖）"""
        raise NotImplementedError(f"{self.__class__.__name__} 不支持 Embedding 功能")

    def __repr__(self):
        return f"<{self.__class__.__name__} model={self.model}>"


# ============================================================
# DashScope (通义千问) Provider
# ============================================================
class DashScopeProvider(BaseLLMProvider):
    """通义千问系列：qwen-plus, qwen-max, qwen-vl-plus 等
    
    支持两种接入方式:
    1. DashScope 通用 API: https://dashscope.aliyuncs.com/
    2. 百炼平台专属 API: https://xxx.cn-beijing.maas.aliyuncs.com/
       (在 .env 中设置 DASHSCOPE_BASE_URL 即可切换)
    """

    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    EMBED_BASE_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"

    VISION_MODELS = {"qwen-vl-plus", "qwen-vl-max", "qwen-vl-plus-latest", "qwen-vl-max-latest"}

    def __init__(self, api_key: str = None, model: str = "qwen-plus",
                 temperature: float = 0.7, max_tokens: int = 2000,
                 base_url: str = None):
        super().__init__(
            api_key=api_key or settings.DASHSCOPE_API_KEY,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # 百炼平台 workspace 专属地址 > 环境变量 > 默认 DashScope 地址
        custom_base = base_url or getattr(settings, 'DASHSCOPE_BASE_URL', '')
        if custom_base:
            self.BASE_URL = custom_base.rstrip('/') + '/chat/completions'
            self.EMBED_BASE_URL = custom_base.rstrip('/') + '/embeddings/text-embedding'

    @property
    def supports_vision(self) -> bool:
        """通义千问 VL 系列支持图片输入"""
        return any(vm in self.model.lower() for vm in self.VISION_MODELS)

    def chat(self, messages: list, **kwargs) -> str:
        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        payload.update(kwargs)

        resp = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def chat_stream(self, messages: list, **kwargs) -> Generator[str, None, None]:
        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        payload.update(kwargs)

        resp = requests.post(self.BASE_URL, headers=headers, json=payload, stream=True, timeout=120)
        resp.raise_for_status()

        for line in resp.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except json.JSONDecodeError:
                        continue

    def embed(self, text: str) -> list:
        """使用 text-embedding-v3 进行向量化"""
        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "text-embedding-v3",
            "input": {"texts": [text]},
            "parameters": {"text_type": "query"},
        }
        resp = requests.post(self.EMBED_BASE_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["output"]["embeddings"][0]["embedding"]


# ============================================================
# DeepSeek Provider
# ============================================================
class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek 系列：deepseek-chat, deepseek-coder 等
    注册: https://platform.deepseek.com/
    API Key 放在 .env: DEEPSEEK_API_KEY=sk-xxx
    """

    BASE_URL = "https://api.deepseek.com/v1/chat/completions"

    def __init__(self, api_key: str = None, model: str = "deepseek-chat",
                 temperature: float = 0.7, max_tokens: int = 4096):
        super().__init__(
            api_key=api_key or getattr(settings, 'DEEPSEEK_API_KEY', ''),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def chat(self, messages: list, **kwargs) -> str:
        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        payload.update(kwargs)

        resp = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def chat_stream(self, messages: list, **kwargs) -> Generator[str, None, None]:
        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        payload.update(kwargs)

        resp = requests.post(self.BASE_URL, headers=headers, json=payload, stream=True, timeout=120)
        resp.raise_for_status()

        for line in resp.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except json.JSONDecodeError:
                        continue


# ============================================================
# GLM (智谱清言) Provider
# ============================================================
class GLMProvider(BaseLLMProvider):
    """智谱 AI 系列：glm-4, glm-4-flash 等
    注册: https://open.bigmodel.cn/
    API Key 放在 .env: GLM_API_KEY=xxx
    """

    BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    def __init__(self, api_key: str = None, model: str = "glm-4-flash",
                 temperature: float = 0.7, max_tokens: int = 4096):
        super().__init__(
            api_key=api_key or getattr(settings, 'GLM_API_KEY', ''),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def chat(self, messages: list, **kwargs) -> str:
        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        payload.update(kwargs)

        resp = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def chat_stream(self, messages: list, **kwargs) -> Generator[str, None, None]:
        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        payload.update(kwargs)

        resp = requests.post(self.BASE_URL, headers=headers, json=payload, stream=True, timeout=120)
        resp.raise_for_status()

        for line in resp.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except json.JSONDecodeError:
                        continue

    def embed(self, text: str) -> list:
        """GLM 不支持 Embedding，使用千问作为后备"""
        fallback = DashScopeProvider()
        return fallback.embed(text)


# ============================================================
# Provider 工厂
# ============================================================
class LLMProviderFactory:
    """统一工厂：根据名称返回对应的 Provider 实例

    用法:
        provider = LLMProviderFactory.create('deepseek', model='deepseek-chat')
        answer = provider.chat([{"role": "user", "content": "你好"}])
        for chunk in provider.chat_stream(messages):
            print(chunk, end="")
    """

    PROVIDERS = {
        'dashscope': DashScopeProvider,
        'qwen': DashScopeProvider,          # 别名
        'tongyi': DashScopeProvider,        # 别名
        'deepseek': DeepSeekProvider,
        'glm': GLMProvider,
        'zhipu': GLMProvider,               # 别名
    }

    @classmethod
    def create(cls, provider_name: str, **kwargs) -> BaseLLMProvider:
        """创建 Provider 实例

        Args:
            provider_name: 'dashscope' | 'deepseek' | 'glm'
            **kwargs: 透传给 Provider 构造函数 (model, temperature, max_tokens 等)
        """
        name = provider_name.lower()
        if name not in cls.PROVIDERS:
            available = ', '.join(sorted(set(cls.PROVIDERS.keys())))
            raise ValueError(f"不支持的 Provider: {name}。可用: {available}")

        return cls.PROVIDERS[name](**kwargs)

    @classmethod
    def create_all(cls, **kwargs) -> dict:
        """创建所有可用 Provider（需要全部 API Key 配置）

        Returns:
            dict: {'dashscope': BaseLLMProvider, 'deepseek': ..., 'glm': ...}
        """
        result = {}
        for name in ['dashscope', 'deepseek', 'glm']:
            try:
                result[name] = cls.create(name, **kwargs)
            except Exception as e:
                logger.warning(f"创建 Provider {name} 失败: {e}")
        return result
