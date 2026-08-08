"""全链路 Trace：结构化 Span 记录，供评测/监控/审计使用。

设计：每次 Agent 调用生成唯一 trace_id，内部按状态/工具/模型拆成 Span，
形成树状调用链。P2 落内存 + 日志；P3 可接入 Jaeger / OpenTelemetry。

这是 LLM-as-Judge 评测和监控大屏的数据来源（红线：底座以跑通链路为终点，
但 Trace 是 P2 评测与 P3 大屏的共同前置依赖，必须先行）。
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from harness_core.logging import logger


@dataclass
class Span:
    span_id: str
    trace_id: str
    parent_id: Optional[str]
    kind: str  # plan / llm / tool / sandbox / reflect / observe
    name: str
    start_ms: int
    end_ms: Optional[int] = None
    status: str = "running"
    meta: dict[str, Any] = field(default_factory=dict)

    def finish(self, status: str = "ok", **meta: Any) -> None:
        self.end_ms = int(time.time() * 1000)
        self.status = status
        self.meta.update(meta)

    def to_dict(self) -> dict:
        return asdict(self)


class Tracer:
    """单 trace 的 Span 收集器。"""

    def __init__(self, trace_id: Optional[str] = None) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex[:16]
        self.spans: list[Span] = []

    def start(self, kind: str, name: str, parent_id: Optional[str] = None, **meta: Any) -> Span:
        span = Span(
            span_id=uuid.uuid4().hex[:8],
            trace_id=self.trace_id,
            parent_id=parent_id,
            kind=kind,
            name=name,
            start_ms=int(time.time() * 1000),
            meta=meta,
        )
        self.spans.append(span)
        logger.info(f"[Trace] + span {span.span_id} {kind}/{name} trace={self.trace_id}")
        return span

    def summary(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_count": len(self.spans),
            "total_ms": (
                (self.spans[-1].end_ms or int(time.time() * 1000))
                - self.spans[0].start_ms
                if self.spans
                else 0
            ),
            "spans": [s.to_dict() for s in self.spans],
        }
