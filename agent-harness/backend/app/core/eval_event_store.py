"""
AI 功能事件存储（Eval Event Store）

用于记录平台上每一次真实 AI 调用：RAG 问答、AI 用例生成、数据工厂、需求评审等。
EvalCenter 的自动追踪通过轮询本存储，实现"有 AI 调用才刷新"的事件驱动监控。
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 全链路 Trace 上下文（ContextVar，自动透传 trace_id）──
# 业务入口（router.chat 等）调用 TraceContext.set(trace_id) 后，
# 任意底座埋点（LLM路由/工具/向量/DB/网关）都能自动归属到该 trace，
# 无需在每层手动透传 trace_id 参数，实现无侵入的底座子链路挂载。
_trace_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "eval_trace_id", default=None
)


class TraceContext:
    """全链路 trace_id 上下文管理器（基于 contextvars，天然支持 async/线程）。"""

    @staticmethod
    def get() -> Optional[str]:
        return _trace_ctx.get()

    @staticmethod
    def set(trace_id: str) -> "contextvars.Token":
        return _trace_ctx.set(trace_id)

    @staticmethod
    def reset(token: "contextvars.Token") -> None:
        _trace_ctx.reset(token)

    @classmethod
    def bind(cls, trace_id: Optional[str]) -> "TraceScope":
        """返回一个同步上下文管理器；若 trace_id 为空则自动生成一个。"""
        return TraceScope(trace_id)

    @classmethod
    def async_bind(cls, trace_id: Optional[str]) -> "AsyncTraceScope":
        """返回一个异步上下文管理器，供 async def 使用。"""
        return AsyncTraceScope(trace_id)


class _BaseTraceScope:
    """TraceScope / AsyncTraceScope 的公共逻辑。"""

    def __init__(self, trace_id: Optional[str]):
        self._trace_id = trace_id or str(uuid.uuid4())
        self._token: Optional["contextvars.Token"] = None

    def _enter(self) -> str:
        self._token = _trace_ctx.set(self._trace_id)
        return self._trace_id

    def _exit(self) -> None:
        if self._token is not None:
            _trace_ctx.reset(self._token)


class TraceScope(_BaseTraceScope):
    """with TraceContext.bind(tid): ... 的同步上下文管理器实现。"""

    def __enter__(self) -> str:
        return self._enter()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._exit()


class AsyncTraceScope(_BaseTraceScope):
    """async with TraceContext.async_bind(tid): ... 的异步上下文管理器实现。"""

    async def __aenter__(self) -> str:
        return self._enter()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._exit()

DATA_DIR = os.environ.get("EVAL_DATA_DIR", "/app/data")
EVENTS_PATH = os.path.join(DATA_DIR, "eval_events.json")

# 需要被 EvalCenter 监控的 AI 功能模块（对应 task_type / feature）
TRACKED_FEATURES = {
    # ── 业务功能层（RAG / 问答 / 生成）──
    "knowledge_chat",
    "chat",
    "fast_chat",
    "reasoning",
    "rag_query",
    "rag_search",
    "ai_testcase",
    "data_generation",
    "requirement_review",
    "quality_check",
    "agent_loop",
    "evaluate",
    # ── AI 底座链路层（基础设施监控）──
    "llm_router",      # LLM 路由决策
    "tool_call",       # 工具/MCP 调用执行
    "tool_gateway",    # 工具网关调用
    "vector_search",   # 向量检索（Milvus / 本地向量库）
    "db_query",        # 数据库持久化操作
}

# 友好显示名称
FEATURE_LABELS = {
    "knowledge_chat": "AI 知识库问答",
    "chat": "AI 日常问答",
    "fast_chat": "AI 快速问答",
    "reasoning": "AI 深度思考",
    "rag_query": "RAG 问答",
    "rag_search": "RAG 检索",
    "ai_testcase": "AI 用例生成",
    "data_generation": "数据工厂",
    "requirement_review": "需求评审",
    "quality_check": "质量检查",
    "agent_loop": "Agent 编排",
    "evaluate": "AI 评测",
    # AI 底座链路层
    "llm_router": "LLM 路由决策",
    "tool_call": "工具调用执行",
    "tool_gateway": "工具网关调用",
    "vector_search": "向量检索",
    "db_query": "数据库操作",
}

# 基础设施层功能（用于前端区分"业务功能"与"AI 底座"标签）
INFRA_FEATURES = {
    "llm_router",
    "tool_call",
    "tool_gateway",
    "vector_search",
    "db_query",
}


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class EvalEvent:
    event_id: str
    timestamp: str  # ISO-8601 UTC
    feature: str
    task_type: str
    model: str
    provider: str
    input_summary: str
    output_summary: str
    latency_ms: int
    token_usage: int
    trace_id: str
    retrieved_docs: List[Dict] = field(default_factory=list)
    status: str = "completed"  # completed / judging / failed
    judge: Optional[Dict] = None
    dimension_scores: Optional[Dict] = None
    issues: List[str] = field(default_factory=list)
    trace_steps: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at_ms: int = field(default_factory=_now_ms)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "feature": self.feature,
            "task_type": self.task_type,
            "model": self.model,
            "provider": self.provider,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "latency_ms": self.latency_ms,
            "token_usage": self.token_usage,
            "trace_id": self.trace_id,
            "retrieved_docs": self.retrieved_docs,
            "status": self.status,
            "judge": self.judge,
            "dimension_scores": self.dimension_scores,
            "issues": self.issues,
            "trace_steps": self.trace_steps,
            "metadata": self.metadata,
            "created_at_ms": self.created_at_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvalEvent":
        return cls(
            event_id=data.get("event_id", ""),
            timestamp=data.get("timestamp", ""),
            feature=data.get("feature", ""),
            task_type=data.get("task_type", ""),
            model=data.get("model", ""),
            provider=data.get("provider", ""),
            input_summary=data.get("input_summary", ""),
            output_summary=data.get("output_summary", ""),
            latency_ms=int(data.get("latency_ms", 0) or 0),
            token_usage=int(data.get("token_usage", 0) or 0),
            trace_id=data.get("trace_id", ""),
            retrieved_docs=data.get("retrieved_docs") or [],
            status=data.get("status", "completed"),
            judge=data.get("judge"),
            dimension_scores=data.get("dimension_scores"),
            issues=data.get("issues") or [],
            trace_steps=data.get("trace_steps") or [],
            metadata=data.get("metadata") or {},
            created_at_ms=int(data.get("created_at_ms", 0) or 0),
        )


class EvalEventStore:
    """本地 EvalCenter 事件存储：支持业务事件 + 底座 infra 事件 + trace 挂载。""

    def get_trace_panorama(self, trace_id: str) -> List[Dict[str, Any]]:
        """返回指定 trace_id 的 AI 底座工位全景。

        列出所有已注册的底座能力（llm_router/tool/vector/db/gateway），
        并标出本次链路中实际调用了哪些、调用次数、总耗时、关键指标。
        """
        if not trace_id:
            return []
        counts: Dict[str, int] = {}
        latency: Dict[str, int] = {}
        meta: Dict[str, Dict] = {}
        with self._lock:
            for ev in self._events:
                if ev.trace_id != trace_id:
                    continue
                if not (ev.metadata or {}).get("infra"):
                    continue
                feat = ev.feature
                counts[feat] = counts.get(feat, 0) + 1
                latency[feat] = latency.get(feat, 0) + (ev.latency_ms or 0)
                # 保留最近一次的模型/表/工具名等关键元数据
                meta[feat] = {**(meta.get(feat) or {}), **(ev.metadata or {})}
                meta[feat]["latency_ms"] = ev.latency_ms
                meta[feat]["model"] = ev.model or meta[feat].get("model")
        result = []
        for feat in INFRA_FEATURES:
            info = {
                "feature": feat,
                "label": FEATURE_LABELS.get(feat, feat),
                "used": feat in counts,
                "count": counts.get(feat, 0),
                "latency_ms": latency.get(feat, 0),
            }
            if feat in meta:
                info["model"] = meta[feat].get("model")
                info["provider"] = meta[feat].get("provider")
                info["tool"] = meta[feat].get("tool") or meta[feat].get("tool_name")
                info["tables"] = meta[feat].get("tables")
                info["kb_id"] = meta[feat].get("kb_id")
            result.append(info)
        return result
    """线程安全的事件存储，底层为 JSON 文件。"""

    def __init__(self, path: str = EVENTS_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._ensure_dir()
        self._events: List[EvalEvent] = []
        self._load()

    def _ensure_dir(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        except Exception as e:
            logger.warning(f"[EvalEventStore] 创建数据目录失败: {e}")

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                self._events = [EvalEvent.from_dict(item) for item in raw]
        except Exception as e:
            logger.warning(f"[EvalEventStore] 加载失败: {e}")

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump([e.to_dict() for e in self._events], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[EvalEventStore] 保存失败: {e}")

    def add(self, event: EvalEvent) -> str:
        with self._lock:
            self._events.append(event)
            # 限制总数，避免文件无限膨胀（保留最近 2000 条）
            self._events = sorted(self._events, key=lambda x: x.created_at_ms)[-2000:]
            self._save()
        return event.event_id

    def update_judge(
        self,
        event_id: str,
        judge: Dict[str, Any],
        dimension_scores: Dict[str, Any],
        issues: List[str],
    ) -> None:
        with self._lock:
            for ev in self._events:
                if ev.event_id == event_id:
                    ev.judge = judge
                    ev.dimension_scores = dimension_scores
                    ev.issues = issues
                    ev.status = "completed"
                    break
            self._save()

    def update_by_trace_id(
        self,
        trace_id: str,
        judge: Dict[str, Any],
        dimension_scores: Dict[str, Any],
        issues: List[str],
        trace_steps: Optional[List[Dict]] = None,
    ) -> Optional[str]:
        """通过 trace_id 精确回写 Judge 结果和链路步骤（避免 feature/input 前缀匹配失败）。"""
        with self._lock:
            for ev in self._events:
                if ev.trace_id == trace_id:
                    ev.judge = judge
                    ev.dimension_scores = dimension_scores
                    ev.issues = issues
                    ev.status = "completed"
                    if trace_steps is not None:
                        ev.trace_steps = trace_steps
                    self._save()
                    return ev.event_id
        return None

    def append_trace_steps(self, trace_id: str, steps: List[Dict]) -> bool:
        """向已有事件追加 trace_steps（用于把底座子链路挂载到业务 trace 下）。"""
        if not trace_id or not steps:
            return False
        with self._lock:
            for ev in self._events:
                if ev.trace_id == trace_id:
                    existing = list(ev.trace_steps or [])
                    existing.extend(steps)
                    ev.trace_steps = existing
                    self._save()
                    return True
        return False

    def flush_infra_steps(self, trace_id: str) -> bool:
        """业务 trace 收尾时调用：把本次调用过程中已落库、但当时父事件尚不存在、
        导致 append_trace_steps 失败的底座子链路事件，重新挂载到父 trace 上。

        机制：底座埋点在父事件创建前先以 INFRA_FEATURES 落库（同一 trace_id），
        此处扫描这些 infra 事件，提取其 trace_steps 并合并进父事件，然后标记已挂载、
        避免重复。这样无论父子事件创建顺序如何，底座子链路都能正确归属。
        """
        if not trace_id:
            return False
        infra_steps: List[Dict] = []
        with self._lock:
            parent = None
            for ev in self._events:
                if ev.trace_id == trace_id and not (ev.metadata or {}).get("infra"):
                    parent = ev
                    break
            if parent is None:
                return False
            for ev in self._events:
                if ev.trace_id != trace_id:
                    continue
                if not (ev.metadata or {}).get("infra"):
                    continue
                if (ev.metadata or {}).get("_mounted_to_parent"):
                    continue
                infra_steps.extend(ev.trace_steps or [])
                ev.metadata = {**(ev.metadata or {}), "_mounted_to_parent": True}
            if infra_steps:
                existing = list(parent.trace_steps or [])
                # 去重：避免重复挂载同一项
                seen_ids = {s.get("step_id") for s in existing if s.get("step_id")}
                for s in infra_steps:
                    if s.get("step_id") and s.get("step_id") in seen_ids:
                        continue
                    existing.append(s)
                parent.trace_steps = existing
                self._save()
                return True
        return False

    def attach_judge_to_latest(
        self,
        feature: str,
        input_text: str,
        judge: Dict[str, Any],
        dimension_scores: Dict[str, Any],
        issues: List[str],
    ) -> Optional[str]:
        """把 Judge 结果关联到最近的同 feature + 同输入前缀的 LLM 调用事件上。"""
        if not input_text:
            return None
        needle = _summarize(input_text, 80)
        with self._lock:
            candidates = sorted(
                [e for e in self._events if e.feature == feature and e.input_summary.startswith(needle)],
                key=lambda x: x.created_at_ms,
                reverse=True,
            )
            if candidates:
                ev = candidates[0]
                ev.judge = judge
                ev.dimension_scores = dimension_scores
                ev.issues = issues
                ev.status = "completed"
                self._save()
                return ev.event_id
        return None

    def list(
        self,
        feature: Optional[str] = None,
        since_ms: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EvalEvent]:
        with self._lock:
            events = list(self._events)
        events = sorted(events, key=lambda x: x.created_at_ms, reverse=True)
        if feature:
            events = [e for e in events if e.feature == feature]
        if since_ms is not None:
            events = [e for e in events if e.created_at_ms > since_ms]
        return events[offset : offset + limit]

    def get(self, event_id: str) -> Optional[EvalEvent]:
        with self._lock:
            for ev in self._events:
                if ev.event_id == event_id:
                    return ev
        return None

    def latest_ms(self) -> int:
        with self._lock:
            if not self._events:
                return 0
            return max(e.created_at_ms for e in self._events)

    def stats_by_feature(self, hours: int = 24) -> Dict[str, Any]:
        """按功能模块聚合最近 N 小时的统计。"""
        cutoff = _now_ms() - hours * 3600 * 1000
        with self._lock:
            events = [e for e in self._events if e.created_at_ms >= cutoff]
        stats: Dict[str, Dict[str, Any]] = {}
        for e in events:
            label = FEATURE_LABELS.get(e.feature, e.feature)
            if e.feature not in stats:
                stats[e.feature] = {
                    "feature": e.feature,
                    "label": label,
                    "count": 0,
                    "total_latency_ms": 0,
                    "total_tokens": 0,
                    "avg_score": 0.0,
                    "score_sum": 0.0,
                    "score_count": 0,
                }
            s = stats[e.feature]
            s["count"] += 1
            s["total_latency_ms"] += e.latency_ms
            s["total_tokens"] += e.token_usage
            if e.judge and "overall" in e.judge:
                s["score_sum"] += float(e.judge["overall"])
                s["score_count"] += 1
        for s in stats.values():
            s["avg_latency_ms"] = round(s["total_latency_ms"] / max(s["count"], 1), 1)
            s["avg_tokens"] = round(s["total_tokens"] / max(s["count"], 1), 1)
            s["avg_score"] = round(s["score_sum"] / max(s["score_count"], 1), 2)
        return stats


_eval_event_store: Optional[EvalEventStore] = None


def get_eval_event_store(path: Optional[str] = None) -> EvalEventStore:
    global _eval_event_store
    if _eval_event_store is None:
        _eval_event_store = EvalEventStore(path or EVENTS_PATH)
    return _eval_event_store


def is_tracked_feature(task_type: str) -> bool:
    return task_type in TRACKED_FEATURES


def build_event(
    feature: str,
    task_type: str,
    model: str,
    provider: str,
    input_text: str,
    output_text: str,
    latency_ms: int,
    token_usage: int = 0,
    trace_id: Optional[str] = None,
    retrieved_docs: Optional[List[Dict]] = None,
    trace_steps: Optional[List[Dict]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    status: str = "completed",
) -> EvalEvent:
    now = datetime.now(timezone.utc)
    steps = trace_steps or []
    # 给每个 trace_step 分配唯一 step_id，便于 EvalCenter 去重/稳定 key
    for s in steps:
        if not s.get("step_id"):
            s["step_id"] = str(uuid.uuid4())
    return EvalEvent(
        event_id=str(uuid.uuid4()),
        timestamp=now.isoformat(),
        feature=feature,
        task_type=task_type,
        model=model or "unknown",
        provider=provider or "unknown",
        input_summary=_summarize(input_text),
        output_summary=_summarize(output_text),
        latency_ms=latency_ms,
        token_usage=token_usage,
        trace_id=trace_id or str(uuid.uuid4()),
        retrieved_docs=retrieved_docs or [],
        trace_steps=steps,
        metadata=metadata or {},
        status=status,
    )


def record_infra_event(
    feature: str,
    task_type: str,
    input_text: str,
    output_text: str = "",
    latency_ms: int = 0,
    model: str = "",
    provider: str = "",
    trace_steps: Optional[List[Dict]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    status: str = "completed",
    trace_id: Optional[str] = None,
) -> Optional[str]:
    """AI 底座链路轻量埋点（不触发 Judge 评分，仅做全链路追踪）。

    Args:
        feature: 功能模块标识（如 llm_router / tool_call / vector_search / db_query / tool_gateway）
        task_type: 同 feature（底座层 feature 即 task_type）
        input_text: 调用入参摘要
        output_text: 调用返回摘要
        latency_ms: 耗时
        trace_steps: 链路步骤（可选，若调用方已实现精细步骤可传入）
        metadata: 附加数据（如 tool_name / collection / sql 等）
        status: completed / failed
    """
    if task_type not in TRACKED_FEATURES:
        return None
    try:
        token = 0
        try:
            token = int(len((input_text or "") + (output_text or "")) / 4)
        except Exception:
            token = 0
        # 显式传入优先；否则自动从全链路 TraceContext 取（无侵入挂载底座子链路）
        effective_trace_id = trace_id or TraceContext.get()
        # 若未显式传入 trace_steps，则按默认步骤构造一条链路记录
        # 底座功能映射到标准可视化类型，EvalCenter 才能按工位展示正确图标/颜色
        if not trace_steps:
            infra_type_map = {
                "tool_call": "tool",
                "tool_gateway": "tool",
                "vector_search": "retrieve",
                "db_query": "db",
                "llm_router": "route",
            }
            trace_steps = [{
                "type": infra_type_map.get(feature, "tool"),
                "title": FEATURE_LABELS.get(feature, feature),
                "status": status,
                "metadata": metadata or {},
            }]
        ev = build_event(
            feature=feature,
            task_type=task_type,
            model=model,
            provider=provider,
            input_text=input_text,
            output_text=output_text,
            latency_ms=latency_ms,
            token_usage=token,
            trace_id=effective_trace_id,
            trace_steps=trace_steps,
            metadata={**(metadata or {}), "infra": True},
            status=status,
        )
        get_eval_event_store().add(ev)
        # 若关联到了业务 trace，把当前底座步骤追加到父业务事件的 trace_steps 里，
        # 这样业务 trace 回放时能看到完整的底座子链路。
        if effective_trace_id:
            try:
                get_eval_event_store().append_trace_steps(effective_trace_id, trace_steps)
            except Exception:
                pass
        return ev.event_id
    except Exception as e:
        logger.warning(f"[EvalEventStore] 底座埋点失败({feature}): {e}")
        return None


def _summarize(text: str, max_len: int = 300) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = text.strip().replace("\n", " ")
    return text if len(text) <= max_len else text[:max_len] + "..."
