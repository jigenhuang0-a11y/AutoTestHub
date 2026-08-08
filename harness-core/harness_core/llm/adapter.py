"""L1 模型底座 - DeepSeek / 通义千问适配器实现。

仅依赖 httpx 直连 OpenAI 兼容接口，不引入 langchain / langgraph 等重框架。
主力：DeepSeek；备用：通义千问（qwen）。
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx
from pydantic import BaseModel

from harness_core.config import settings
from harness_core.llm.base import (
    ChatMessage,
    ChatResponse,
    ModelAdapter,
)
from harness_core.logging import logger


def _to_openai_payload(
    messages: list[ChatMessage],
    *,
    temperature: float,
    max_tokens: int,
    stream: bool = False,
) -> dict:
    return {
        "model": "",
        "messages": [m.__dict__ for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }


def _count_tokens_approx(text: str) -> int:
    """粗略 token 估算（中文约 1.5 字符/token，英文约 4 字符/token）。

    P1 用近似法即可；P2 可换 tiktoken / 模型方 tokenizer。
    """
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    non_cjk = len(text) - cjk
    return int(cjk / 1.5 + non_cjk / 4) + 1


class OpenAICompatibleAdapter(ModelAdapter):
    """OpenAI 兼容协议适配器，DeepSeek / 通义千问通用。"""

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
    ) -> None:
        self.name = name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> ChatResponse:
        payload = _to_openai_payload(
            messages, temperature=temperature, max_tokens=max_tokens
        )
        payload["model"] = self._model
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return ChatResponse(
            content=content,
            model=self._model,
            prompt_tokens=usage.get("prompt_tokens", 0)
            or _count_tokens_approx(
                " ".join(m.content for m in messages)
            ),
            completion_tokens=usage.get("completion_tokens", 0)
            or _count_tokens_approx(content),
            raw=data,
        )

    async def embedding(self, texts: list[str]) -> list[list[float]]:
        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        out: list[list[float]] = []
        async with httpx.AsyncClient(timeout=60) as client:
            for text in texts:
                resp = await client.post(
                    url,
                    json={"model": self._model, "input": text},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                out.append(data["data"][0]["embedding"])
        return out

    async def stream_chat(
        self, messages: list[ChatMessage], **kwargs: Any
    ) -> AsyncIterator[str]:
        """真正的流式输出：解析 OpenAI SSE 流。"""
        payload = _to_openai_payload(
            messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2048),
            stream=True,
        )
        payload["model"] = self._model
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST", url, json=payload, headers=headers
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta


class DeepSeekAdapter(OpenAICompatibleAdapter):
    def __init__(self) -> None:
        super().__init__(
            name="deepseek-chat",
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        )


class QwenAdapter(OpenAICompatibleAdapter):
    def __init__(self) -> None:
        super().__init__(
            name="qwen-plus",
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
            model=settings.qwen_model,
        )
