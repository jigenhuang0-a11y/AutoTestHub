"""监控指标收集器（P3）。

聚合模型网关埋点，供监控大屏使用。P3 内存版（进程内环形缓冲），P4 落 MySQL/时序库。

采集维度：调用次数、Token 消耗（in/out）、按模型分布、错误计数、最近 Trace。
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    errors: int = 0


class MetricsCollector:
    def __init__(self) -> None:
        self._by_model: dict[str, _Bucket] = defaultdict(_Bucket)
        self._total = _Bucket()
        self._recent_traces: list[dict] = []
        self._start = time.monotonic()

    def record_call(self, *, model: str, in_tokens: int, out_tokens: int, error: bool = False) -> None:
        b = self._by_model[model]
        b.calls += 1
        b.prompt_tokens += in_tokens
        b.completion_tokens += out_tokens
        if error:
            b.errors += 1
        self._total.calls += 1
        self._total.prompt_tokens += in_tokens
        self._total.completion_tokens += out_tokens
        if error:
            self._total.errors += 1

    def record_trace(self, trace_id: str, kind: str, ok: bool = True) -> None:
        self._recent_traces.append({
            "trace_id": trace_id, "kind": kind, "ok": ok, "ts": int(time.time() * 1000),
        })
        if len(self._recent_traces) > 100:
            self._recent_traces.pop(0)

    def snapshot(self) -> dict:
        uptime = int(time.monotonic() - self._start)
        err_rate = (self._total.errors / self._total.calls) if self._total.calls else 0.0
        return {
            "uptime_seconds": uptime,
            "total_calls": self._total.calls,
            "total_prompt_tokens": self._total.prompt_tokens,
            "total_completion_tokens": self._total.completion_tokens,
            "error_rate": round(err_rate, 4),
            "by_model": {
                m: {
                    "calls": b.calls,
                    "prompt_tokens": b.prompt_tokens,
                    "completion_tokens": b.completion_tokens,
                    "errors": b.errors,
                }
                for m, b in self._by_model.items()
            },
            "recent_traces": self._recent_traces[-20:],
        }


metrics = MetricsCollector()
