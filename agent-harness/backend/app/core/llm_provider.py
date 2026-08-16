"""
统一 LLM Provider 抽象层（去 Django 依赖版）
支持：DashScope(千问)、DeepSeek、GLM(智谱)、Ollama(本地)

Langfuse 集成：
- 所有 chat / chat_raw / chat_stream 调用自动创建 trace/generation
- 业务方可通过 __langfuse_name / __langfuse_session_id / __langfuse_user_id /
  __langfuse_meta 等关键字传入追踪信息
- 未配置 LANGFUSE_PUBLIC_KEY 时自动降级为 no-op，不影响本地开发
"""
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, Optional, Tuple

from app.core.langfuse_client import StreamTracer, trace_llm_call

logger = logging.getLogger(__name__)


def _pop_langfuse_kwargs(kwargs: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[str], Dict[str, Any]]:
    """从 kwargs 中提取 Langfuse 追踪参数并返回，剩余 kwargs 保持原样。"""
    name = kwargs.pop("__langfuse_name", "llm_chat") or "llm_chat"
    session_id = kwargs.pop("__langfuse_session_id", None)
    user_id = kwargs.pop("__langfuse_user_id", None)
    meta = kwargs.pop("__langfuse_meta", {}) or {}
    if not isinstance(meta, dict):
        meta = {}
    return name, session_id, user_id, meta


class BaseLLMProvider(ABC):
    """LLM Provider 抽象基类"""

    def __init__(self, api_key: str, model: str, temperature: float = 0.7, max_tokens: int = 2000):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    def chat(self, messages: list, **kwargs) -> str:
        ...

    @abstractmethod
    def chat_stream(self, messages: list, **kwargs) -> Generator[dict, None, None]:
        ...

    def chat_raw(self, messages: list, **kwargs) -> dict:
        """
        返回完整 API 响应 dict（含 tool_calls 等），供 ReAct/Agent 使用。

        Returns:
            {
                "content": str | None,
                "tool_calls": list | None,
                "model": str,
                "usage": dict,
            }
        """
        lf_name, lf_session_id, lf_user_id, lf_meta = _pop_langfuse_kwargs(kwargs)
        with trace_llm_call(
            name=lf_name or "llm_chat_raw",
            model=self.model,
            messages=messages,
            metadata={**lf_meta, "provider": self.__class__.__name__},
            session_id=lf_session_id,
            user_id=lf_user_id,
        ) as ctx:
            import requests
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
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
            choice = data["choices"][0]
            result = {
                "content": choice["message"].get("content"),
                "tool_calls": choice["message"].get("tool_calls"),
                "model": data.get("model", self.model),
                "usage": data.get("usage", {}),
            }
            ctx["generation"].update(
                output=str(result.get("content", ""))[:4000],
                usage=result.get("usage", {}),
            )
            return result

    def __repr__(self):
        return f"<{self.__class__.__name__} model={self.model}>"


class DashScopeProvider(BaseLLMProvider):
    """通义千问 Provider"""

    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    def __init__(self, api_key: str = None, model: str = "qwen-plus",
                 temperature: float = 0.7, max_tokens: int = 2000,
                 base_url: str = None):
        super().__init__(
            api_key=api_key or os.getenv("DASHSCOPE_API_KEY"),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        custom_base = base_url or os.getenv("DASHSCOPE_BASE_URL", "")
        if custom_base:
            self.BASE_URL = custom_base.rstrip("/") + "/chat/completions"

    def chat(self, messages: list, **kwargs) -> str:
        lf_name, lf_session_id, lf_user_id, lf_meta = _pop_langfuse_kwargs(kwargs)
        with trace_llm_call(
            name=lf_name or "llm_chat",
            model=self.model,
            messages=messages,
            metadata={**lf_meta, "provider": self.__class__.__name__},
            session_id=lf_session_id,
            user_id=lf_user_id,
        ) as ctx:
            import requests
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
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
            content = data["choices"][0]["message"]["content"]
            ctx["generation"].update(output=content[:4000])
            return content

    def chat_stream(self, messages: list, **kwargs) -> Generator[dict, None, None]:
        lf_name, lf_session_id, lf_user_id, lf_meta = _pop_langfuse_kwargs(kwargs)
        tracer = StreamTracer(
            name=lf_name or "llm_chat_stream",
            model=self.model,
            messages=messages,
            metadata={**lf_meta, "provider": self.__class__.__name__},
            session_id=lf_session_id,
            user_id=lf_user_id,
        )
        full = []
        with tracer:
            import requests
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
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
                            if "content" in delta and delta["content"]:
                                full.append(delta["content"])
                                yield {"type": "delta", "content": delta["content"]}
                        except json.JSONDecodeError:
                            continue
        tracer.record_output("".join(full))
        yield {"type": "done", "content": "".join(full)}


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek Provider"""

    BASE_URL = "https://api.deepseek.com/v1/chat/completions"

    def __init__(self, api_key: str = None, model: str = "deepseek-chat",
                 temperature: float = 0.7, max_tokens: int = 4096):
        super().__init__(
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY"),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def chat(self, messages: list, **kwargs) -> str:
        lf_name, lf_session_id, lf_user_id, lf_meta = _pop_langfuse_kwargs(kwargs)
        with trace_llm_call(
            name=lf_name or "llm_chat",
            model=self.model,
            messages=messages,
            metadata={**lf_meta, "provider": self.__class__.__name__},
            session_id=lf_session_id,
            user_id=lf_user_id,
        ) as ctx:
            import requests
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
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
            content = data["choices"][0]["message"]["content"]
            ctx["generation"].update(output=content[:4000])
            return content

    REASONING_MODEL = "deepseek-reasoner"

    def chat_stream(self, messages: list, enable_reasoning: bool = False, **kwargs) -> Generator[dict, None, None]:
        lf_name, lf_session_id, lf_user_id, lf_meta = _pop_langfuse_kwargs(kwargs)
        # 开启推理时路由到原生 reasoner 模型
        model = self.REASONING_MODEL if enable_reasoning else self.model
        tracer = StreamTracer(
            name=lf_name or "llm_chat_stream",
            model=model,
            messages=messages,
            metadata={**lf_meta, "provider": self.__class__.__name__, "enable_reasoning": enable_reasoning},
            session_id=lf_session_id,
            user_id=lf_user_id,
        )
        full = []
        with tracer:
            import requests
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
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
                            if "reasoning_content" in delta and delta["reasoning_content"]:
                                yield {"type": "reasoning", "content": delta["reasoning_content"]}
                            if "content" in delta and delta["content"]:
                                full.append(delta["content"])
                                yield {"type": "delta", "content": delta["content"]}
                        except json.JSONDecodeError:
                            continue
        tracer.record_output("".join(full))
        yield {"type": "done", "content": "".join(full)}


class GLMProvider(BaseLLMProvider):
    """智谱 GLM Provider"""

    BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    def __init__(self, api_key: str = None, model: str = "glm-4-flash",
                 temperature: float = 0.7, max_tokens: int = 4096):
        super().__init__(
            api_key=api_key or os.getenv("GLM_API_KEY"),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def chat(self, messages: list, **kwargs) -> str:
        lf_name, lf_session_id, lf_user_id, lf_meta = _pop_langfuse_kwargs(kwargs)
        with trace_llm_call(
            name=lf_name or "llm_chat",
            model=self.model,
            messages=messages,
            metadata={**lf_meta, "provider": self.__class__.__name__},
            session_id=lf_session_id,
            user_id=lf_user_id,
        ) as ctx:
            import requests
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
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
            content = data["choices"][0]["message"]["content"]
            ctx["generation"].update(output=content[:4000])
            return content

    def chat_stream(self, messages: list, **kwargs) -> Generator[dict, None, None]:
        lf_name, lf_session_id, lf_user_id, lf_meta = _pop_langfuse_kwargs(kwargs)
        tracer = StreamTracer(
            name=lf_name or "llm_chat_stream",
            model=self.model,
            messages=messages,
            metadata={**lf_meta, "provider": self.__class__.__name__},
            session_id=lf_session_id,
            user_id=lf_user_id,
        )
        full = []
        with tracer:
            import requests
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
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
                            if "content" in delta and delta["content"]:
                                full.append(delta["content"])
                                yield {"type": "delta", "content": delta["content"]}
                        except json.JSONDecodeError:
                            continue
        tracer.record_output("".join(full))
        yield {"type": "done", "content": "".join(full)}


class OllamaProvider(BaseLLMProvider):
    """Ollama 本地 LLM Provider（隐私优先）

    使用 Ollama 的 OpenAI 兼容 API（v1/chat/completions）。
    支持的蒸馏/量化模型:
        - qwen2.5:7b / qwen2.5:14b  （通义千问蒸馏版）
        - deepseek-r1:8b / deepseek-r1:14b  （DeepSeek R1 蒸馏版）
        - llama3.1:8b  （Meta LLaMA 3.1）
        - mistral:7b  （Mistral 7B）

    用法:
        1. 安装 Ollama: https://ollama.com
        2. ollama pull qwen2.5:7b
        3. 设置环境变量 OLLAMA_BASE_URL=http://localhost:11434/v1
        4. 使用 provider_name="ollama"
    """

    def __init__(self, api_key: str = "ollama", model: str = "qwen2.5:7b",
                 temperature: float = 0.7, max_tokens: int = 4096,
                 base_url: str = None):
        super().__init__(
            api_key=api_key,  # Ollama 不需要真 Key，但接口要求非空
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.BASE_URL = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")).rstrip("/") + "/chat/completions"

    def chat(self, messages: list, **kwargs) -> str:
        lf_name, lf_session_id, lf_user_id, lf_meta = _pop_langfuse_kwargs(kwargs)
        with trace_llm_call(
            name=lf_name or "llm_chat",
            model=self.model,
            messages=messages,
            metadata={**lf_meta, "provider": self.__class__.__name__},
            session_id=lf_session_id,
            user_id=lf_user_id,
        ) as ctx:
            import requests
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": False,
            }
            payload.update(kwargs)
            resp = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            ctx["generation"].update(output=content[:4000])
            return content

    def chat_stream(self, messages: list, **kwargs) -> Generator[dict, None, None]:
        lf_name, lf_session_id, lf_user_id, lf_meta = _pop_langfuse_kwargs(kwargs)
        tracer = StreamTracer(
            name=lf_name or "llm_chat_stream",
            model=self.model,
            messages=messages,
            metadata={**lf_meta, "provider": self.__class__.__name__},
            session_id=lf_session_id,
            user_id=lf_user_id,
        )
        full = []
        with tracer:
            import requests
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True,
            }
            payload.update(kwargs)
            resp = requests.post(self.BASE_URL, headers=headers, json=payload, stream=True, timeout=300)
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
                            if "content" in delta and delta["content"]:
                                full.append(delta["content"])
                                yield {"type": "delta", "content": delta["content"]}
                        except json.JSONDecodeError:
                            continue
        tracer.record_output("".join(full))
        yield {"type": "done", "content": "".join(full)}


class LLMProviderFactory:
    """Provider 工厂"""

    PROVIDERS = {
        "dashscope": DashScopeProvider,
        "qwen": DashScopeProvider,
        "tongyi": DashScopeProvider,
        "deepseek": DeepSeekProvider,
        "glm": GLMProvider,
        "zhipu": GLMProvider,
        "ollama": OllamaProvider,
        "local": OllamaProvider,  # 别名，更语义化
    }

    @classmethod
    def create(cls, provider_name: str, **kwargs) -> BaseLLMProvider:
        name = provider_name.lower()
        if name not in cls.PROVIDERS:
            available = ", ".join(sorted(set(cls.PROVIDERS.keys())))
            raise ValueError(f"不支持的 Provider: {name}。可用: {available}")
        return cls.PROVIDERS[name](**kwargs)
