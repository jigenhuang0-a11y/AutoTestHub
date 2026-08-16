"""
Langfuse 可观测性客户端

负责初始化 Langfuse SDK、给 LLM 调用自动打 trace/span/generation，
并把 Judge LLM 的多维评分作为 Score 挂到对应 trace。

特性：
- 未配置 LANGFUSE_PUBLIC_KEY 时自动降级为 no-op，不阻塞本地开发
- 统一封装 trace 上下文，支持同步和流式两种调用模式
- 所有埋点失败都被捕获并记录为 warning，不污染主业务
"""
import os
import logging
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Optional, Callable

logger = logging.getLogger(__name__)


class _NoOpLangfuse:
    """本地未配置 Langfuse 时的空实现，保证调用方无需 if 判断。"""

    def trace(self, **kwargs):
        return self

    def span(self, **kwargs):
        return self

    def generation(self, **kwargs):
        return self

    def score(self, **kwargs):
        return self

    def update(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _NoOpClient:
    """空客户端，所有方法都返回 _NoOpLangfuse。"""

    def trace(self, **kwargs):
        return _NoOpLangfuse()

    def flush(self, *args, **kwargs):
        pass


_LANGFUSE_CLIENT: Optional[Any] = None
_NO_OP = _NoOpClient()


def _build_host(raw: Optional[str]) -> str:
    if not raw:
        return ""
    host = raw.rstrip("/")
    # Langfuse V2 SDK 要求 host 以 /api 结尾
    if not host.endswith("/api"):
        host = host + "/api"
    return host


def get_langfuse() -> Any:
    """获取 Langfuse 客户端，未配置则返回 no-op。"""
    global _LANGFUSE_CLIENT
    if _LANGFUSE_CLIENT is not None:
        return _LANGFUSE_CLIENT

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    host = _build_host(os.getenv("LANGFUSE_HOST", "").strip())

    if not public_key or not secret_key or not host:
        logger.info(
            "[Langfuse] 未配置 LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST，跳过可观测性上报"
        )
        _LANGFUSE_CLIENT = _NO_OP
        return _LANGFUSE_CLIENT

    try:
        from langfuse import Langfuse
        _LANGFUSE_CLIENT = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            release=os.getenv("LANGFUSE_RELEASE", os.getenv("GIT_COMMIT", "")),
            debug=os.getenv("LANGFUSE_DEBUG", "false").lower() == "true",
        )
        logger.info(f"[Langfuse] 客户端已初始化: host={host}")
    except Exception as e:
        logger.warning(f"[Langfuse] 初始化失败，降级为 no-op: {e}")
        _LANGFUSE_CLIENT = _NO_OP

    return _LANGFUSE_CLIENT


def is_enabled() -> bool:
    """Langfuse 是否已真实启用。"""
    return get_langfuse() is not _NO_OP


def _truncate(text: str, max_len: int = 8000) -> str:
    if not isinstance(text, str):
        text = str(text)
    return text if len(text) <= max_len else text[:max_len] + "\n... [truncated]"


@contextmanager
def trace_llm_call(
    name: str,
    model: str,
    messages: list,
    metadata: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """
    同步 LLM 调用的 trace 上下文。

    用法：
        with trace_llm_call(name="generate_case", model="deepseek-chat", messages=msgs,
                            metadata={"feature": "ai_testcase"}) as ctx:
            output = provider.chat(messages)
            ctx["generation"].update(end_time=..., output=output, usage=...)
    """
    lf = get_langfuse()
    trace_id = str(uuid.uuid4())
    ctx: Dict[str, Any] = {"trace": None, "generation": None, "trace_id": trace_id}

    try:
        trace = lf.trace(
            id=trace_id,
            name=name,
            metadata=metadata or {},
            session_id=session_id,
            user_id=user_id,
        )
        ctx["trace"] = trace

        gen = trace.generation(
            name=f"{name}_generation",
            model=model,
            model_parameters={
                "temperature": getattr(metadata, "temperature", 0.7),
                "max_tokens": getattr(metadata, "max_tokens", 2000),
            },
            input=_truncate(str(messages)),
        )
        ctx["generation"] = gen
    except Exception as e:
        logger.warning(f"[Langfuse] trace 创建失败: {e}")
        yield ctx
        return

    try:
        yield ctx
    finally:
        try:
            lf.flush()
        except Exception as e:
            logger.warning(f"[Langfuse] flush 失败: {e}")


class StreamTracer:
    """流式 LLM 调用的 trace 辅助类，在生成器首尾记录 span/generation。"""

    def __init__(
        self,
        name: str,
        model: str,
        messages: list,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.name = name
        self.model = model
        self.messages = messages
        self.metadata = metadata or {}
        self.session_id = session_id
        self.user_id = user_id
        self._cm = None
        self._ctx = None
        self._gen = None
        self._started = False

    def __enter__(self):
        self._cm = trace_llm_call(
            name=self.name,
            model=self.model,
            messages=self.messages,
            metadata=self.metadata,
            session_id=self.session_id,
            user_id=self.user_id,
        )
        self._ctx = self._cm.__enter__()
        self._gen = self._ctx.get("generation")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cm:
            self._cm.__exit__(exc_type, exc_val, exc_tb)

    def record_output(self, content: str, usage: Optional[Dict] = None):
        if self._gen:
            try:
                self._gen.update(output=_truncate(content), usage=usage or {})
            except Exception as e:
                logger.warning(f"[Langfuse] generation update 失败: {e}")

    def add_score(
        self,
        name: str,
        value: float,
        comment: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        trace = self._ctx.get("trace") if self._ctx else None
        if not trace:
            return
        try:
            trace.score(
                name=name,
                value=float(value),
                comment=_truncate(comment or "", 1000),
                metadata=metadata or {},
            )
        except Exception as e:
            logger.warning(f"[Langfuse] score 失败: {e}")


def score_trace(
    trace_id: str,
    name: str,
    value: float,
    comment: Optional[str] = None,
    metadata: Optional[Dict] = None,
):
    """通过 trace_id 给已存在的 trace 打分（用于异步 Judge）。"""
    lf = get_langfuse()
    if lf is _NO_OP:
        return
    try:
        lf.score(
            trace_id=trace_id,
            name=name,
            value=float(value),
            comment=_truncate(comment or "", 1000),
            metadata=metadata or {},
        )
    except Exception as e:
        logger.warning(f"[Langfuse] score_trace 失败: {e}")


def trace_function(name: Optional[str] = None):
    """装饰器：给任意函数加 trace，name 默认为函数名。"""
    def decorator(func: Callable) -> Callable:
        _name = name or func.__name__

        def wrapper(*args, **kwargs):
            lf = get_langfuse()
            if lf is _NO_OP:
                return func(*args, **kwargs)
            try:
                with lf.trace(name=_name, metadata={"args": args, "kwargs": kwargs}):
                    return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"[Langfuse] trace_function 失败: {e}")
                return func(*args, **kwargs)

        return wrapper

    return decorator
