"""
AI 模型配置工具函数
从数据库 ai_model_config 表读取模型信息，返回可直接调用的 requests 封装。
所有需要调用 LLM 的模块（engine、eval_workflow、views）统一使用此模块。
"""
import json
import logging
import re
from typing import Optional, Generator

from core.harness_client import harness_chat, harness_chat_stream

from .models import AIModelConfig

logger = logging.getLogger(__name__)


def get_active_config(model_id: str = None) -> Optional[AIModelConfig]:
    """
    从数据库获取启用的模型配置。

    Args:
        model_id: 模型ID，如 'deepseek-chat', 'qwen-plus'
                  不传则返回第一个启用的模型（默认）

    Returns:
        AIModelConfig 实例，或 None
    """
    qs = AIModelConfig.objects.filter(is_active=True)
    if model_id:
        qs = qs.filter(model_id=model_id)
    return qs.first()


class ModelClient:
    """
    基于 AIModelConfig 的轻量 HTTP 客户端。
    绕过旧的 LLMProviderFactory，直接用 requests 调用 OpenAI 兼容 API。

    用法：
        client = ModelClient(model_id='deepseek-chat')
        answer = client.chat([{"role": "user", "content": "你好"}])
        for chunk in client.chat_stream([...]):
            print(chunk, end="")
    """

    def __init__(self, model_id: str = None):
        self.config = get_active_config(model_id)
        if not self.config:
            available = list(AIModelConfig.objects.values_list('model_id', flat=True).filter(is_active=True))
            raise ValueError(
                f"未找到可用模型(请求: {model_id}, 已启用: {available})"
                "。请在「模型管理」页面添加并启用至少一个模型。"
            )

    def chat(self, messages: list,
             temperature: float = None,
             max_tokens: int = None,
             **kwargs) -> str:
        """同步对话，返回完整回答。优先走 Agent Harness，失败降级到直连。"""
        try:
            answer = harness_chat(messages, model=self.config.model_id, task_type="ai_evaluator")
            if answer:
                return answer
        except Exception as e:
            logger.warning(f"[ModelClient] Harness 调用失败，将降级: {e}")

        logger.info("[ModelClient] Harness 不可用，降级到本地直连 LLM")
        import requests

        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        payload = {
            'model': self.config.model_id,
            'messages': messages,
            'temperature': temp,
            'max_tokens': tokens,
        }
        payload.update(kwargs)

        resp = requests.post(
            self.config.api_url,
            headers={
                'Authorization': f'Bearer {self.config.api_key}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data['choices'][0]['message']['content']

    def _chat_stream_direct(self, messages: list,
                            temperature: float = None,
                            max_tokens: int = None,
                            **kwargs) -> Generator[str, None, None]:
        """直连 LLM 的流式对话，逐 token 返回。"""
        import requests

        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        payload = {
            'model': self.config.model_id,
            'messages': messages,
            'temperature': temp,
            'max_tokens': tokens,
            'stream': True,
        }
        payload.update(kwargs)

        resp = requests.post(
            self.config.api_url,
            headers={
                'Authorization': f'Bearer {self.config.api_key}',
                'Content-Type': 'application/json',
            },
            json=payload,
            stream=True,
            timeout=self.config.timeout,
        )
        resp.raise_for_status()

        for line in resp.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data:'):
                    data_str = line[5:].strip()
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        if 'content' in delta:
                            yield delta['content']
                    except json.JSONDecodeError:
                        continue

    def chat_stream(self, messages: list,
                    temperature: float = None,
                    max_tokens: int = None,
                    **kwargs) -> Generator[str, None, None]:
        """流式对话，逐 token 返回。优先走 Agent Harness，失败降级到直连。"""
        try:
            stream_iter = harness_chat_stream(
                messages,
                model=self.config.model_id,
                task_type="ai_evaluator",
            )
            first = next(stream_iter, None)
            if first == "":
                logger.info("[ModelClient] Harness stream 不可用，降级到本地直连 LLM")
                for chunk in self._chat_stream_direct(messages, temperature, max_tokens, **kwargs):
                    yield chunk
                return
            if first is not None:
                yield first
            for chunk in stream_iter:
                yield chunk
            return
        except Exception as e:
            logger.warning(f"[ModelClient] Harness stream 调用失败，将降级: {e}")

        logger.info("[ModelClient] Harness stream 不可用，降级到本地直连 LLM")
        for chunk in self._chat_stream_direct(messages, temperature, max_tokens, **kwargs):
            yield chunk

    @property
    def model_id(self):
        return self.config.model_id

    @property
    def provider(self):
        return self.config.provider

    def __repr__(self):
        return f"<ModelClient model={self.config.name} ({self.config.model_id})>"
