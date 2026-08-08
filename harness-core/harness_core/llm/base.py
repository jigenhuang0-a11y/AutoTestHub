"""L1 模型底座 - 统一模型调用抽象。

所有上层业务（插件）禁止直连第三方模型 API，必须经由本层 chat() / embedding()。
这是红线 #1 的物理载体：业务插件只能调中台原语。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional


@dataclass
class ChatMessage:
    role: str  # system / user / assistant / tool
    content: str
    name: Optional[str] = None


@dataclass
class ChatResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict = field(default_factory=dict)


class ModelAdapter(ABC):
    """模型适配器接口：每个第三方模型实现一个子类。"""

    # 适配器唯一标识，对应 settings 中的模型名
    name: str = ""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> ChatResponse:
        ...

    @abstractmethod
    async def embedding(self, texts: list[str]) -> list[list[float]]:
        ...

    async def stream_chat(
        self, messages: list[ChatMessage], **kwargs: Any
    ) -> AsyncIterator[str]:
        """可选：流式输出。默认用非流式结果模拟。"""
        resp = await self.chat(messages, **kwargs)
        yield resp.content
