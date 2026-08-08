"""Trace 存储：P2 内存版（进程内字典），P3 换 MySQL/OTel。"""
from __future__ import annotations

from harness_core.trace.span import Tracer

_TRACES: dict[str, Tracer] = {}


def new_tracer(trace_id: str | None = None) -> Tracer:
    t = Tracer(trace_id)
    _TRACES[t.trace_id] = t
    return t


def get_tracer(trace_id: str) -> Tracer | None:
    return _TRACES.get(trace_id)


def list_traces() -> list[str]:
    return list(_TRACES.keys())
