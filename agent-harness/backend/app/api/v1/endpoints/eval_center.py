"""
全链路评测中心 API

提供：
- 对任意输入/输出执行 Judge LLM 多维评分
- 获取本地聚合的实时监控仪表盘数据
- 返回 Langfuse 外部链接配置
"""
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.eval_store import get_eval_store
from app.core.eval_event_store import get_eval_event_store, FEATURE_LABELS, INFRA_FEATURES
from app.core.hallucination_judge import judge_output

logger = logging.getLogger(__name__)
router = APIRouter()


class JudgeRequest(BaseModel):
    input_text: str = Field(..., description="原始输入 / prompt")
    output_text: str = Field(..., description="模型生成输出")
    reference: str = Field("", description="参考答案 / RAG 检索片段")
    feature: str = Field("unknown", description="业务模块，如 ai_testcase / data_factory / knowledge_chat")
    trace_id: Optional[str] = Field(None, description="关联的 Langfuse trace_id")
    user_id: Optional[str] = Field(None, description="用户 ID")
    session_id: Optional[str] = Field(None, description="会话 ID")


class JudgeResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    message: str = ""


@router.post("/judge", response_model=JudgeResponse)
def run_judge(req: JudgeRequest):
    """对一次 LLM 生成结果执行 Judge 评分，并本地缓存 + 回传 Langfuse。"""
    try:
        result = judge_output(
            input_text=req.input_text,
            output_text=req.output_text,
            reference=req.reference,
            trace_id=req.trace_id,
            feature=req.feature,
            user_id=req.user_id,
            session_id=req.session_id,
        )
        record = result.to_dict()
        record["feature"] = req.feature
        record["input_text"] = req.input_text[:1000]
        record["output_text"] = req.output_text[:1000]
        get_eval_store().save(record)
        # 显式返回标准包装结构，避免旧镜像/代理返回裸对象
        return {"success": True, "data": record, "message": ""}
    except Exception as e:
        logger.error(f"[eval_center] judge 失败: {e}")
        return JudgeResponse(success=False, data={}, message=str(e))


@router.get("/dashboard")
def get_dashboard(
    hours: int = Query(24, ge=1, le=2160),
    granularity: str = Query("auto", pattern="^(auto|hour|week|month)$"),
):
    """获取评测聚合数据。

    - hours: 统计窗口（1~720 小时，默认 24）
    - granularity: 趋势粒度 auto/hour/day。auto 时若窗口内仅 1 个时间点，自动退化为按天聚合。
    """
    return get_eval_event_store().get_dashboard(hours=hours, granularity=granularity)


@router.get("/records")
def list_records(
    feature: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """分页查询评测记录（从追踪事件存储读取）。"""
    store = get_eval_event_store()
    events = store.list(feature=feature, limit=limit, offset=offset)
    records = []
    for e in events:
        rec = e.to_dict()
        rec["overall"] = (e.judge or {}).get("overall", 0)
        rec["hallucination"] = (e.judge or {}).get("hallucination", 0)
        rec["consistency"] = (e.judge or {}).get("consistency", 0)
        rec["completeness"] = (e.judge or {}).get("completeness", 0)
        rec["executability"] = (e.judge or {}).get("executability", 0)
        rec["safety"] = (e.judge or {}).get("safety", 0)
        rec["reason"] = "; ".join(e.issues) if e.issues else ""
        rec["created_at"] = e.timestamp
        records.append(rec)
    return {"records": records, "total": len(store.list(feature=feature, limit=10000))}


@router.get("/langfuse-config")
def get_langfuse_config():
    """返回 Langfuse 外部链接，前端可跳转查看原始 trace。"""
    host = os.getenv("LANGFUSE_HOST", "").rstrip("/")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    return {
        "enabled": bool(host and public_key),
        "host": host,
        "project_url": f"{host}/project" if host else "",
        "traces_url": f"{host}/traces" if host else "",
    }


@router.get("/events")
def list_events(
    feature: Optional[str] = Query(None),
    since_ms: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取最近的 AI 功能调用事件（EvalCenter 自动追踪的数据源）。"""
    store = get_eval_event_store()
    events = store.list(feature=feature, since_ms=since_ms, limit=limit, offset=offset)
    return {
        "events": [e.to_dict() for e in events],
        "latest_ms": store.latest_ms(),
    }


@router.get("/events/{event_id}")
def get_event(event_id: str):
    """获取单个 AI 调用事件的完整过程细节。"""
    ev = get_eval_event_store().get(event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="事件不存在")
    return ev.to_dict()


@router.get("/poll")
def poll_events(since_ms: int = Query(0, ge=0)):
    """EvalCenter 自动追踪轮询端点：返回自 since_ms 以来的新事件与统计。"""
    store = get_eval_event_store()
    events = store.list(since_ms=since_ms, limit=200)
    return {
        "new": len(events) > 0,
        "count": len(events),
        "latest_ms": store.latest_ms(),
        "events": [e.to_dict() for e in events[:20]],
        "stats_by_feature": store.stats_by_feature(),
    }


@router.get("/latest/{feature}")
def get_latest_by_feature(feature: str):
    """取指定功能模块最近一条追踪记录（供卡片点击查看最新详情）。无需鉴权。"""
    events = get_eval_event_store().list(feature=feature, limit=1)
    if not events:
        return {"found": False, "event": None}
    return {"found": True, "event": events[0].to_dict()}


@router.post("/seed-demo")
def seed_demo_trace():
    """往本地事件库注入一条「测试知识库」示例追踪（含底座链路 + 五维评分）。

    用于离线演示 / 面试展示：无需真实调用 LLM，即可让 EvalCenter 卡片点击回放。
    重复调用会追加新事件（trace_id 每次不同）。
    """
    import uuid
    from app.core.eval_event_store import build_event

    trace_id = "seed-kb-" + uuid.uuid4().hex[:12]
    retrieved_docs = [
        {
            "source": "会员退款规则.md",
            "content": "会员退款规则：支持原路退回、余额退回。审核通过后 1-3 个工作日到账。不支持无理由秒退。",
            "score": 0.92,
        },
        {
            "source": "售后政策.pdf",
            "content": "退款申请需在订单完成后 30 天内发起，大额订单需人工复核。",
            "score": 0.78,
        },
    ]
    trace_steps = [
        {
            "type": "route",
            "feature": "llm_router",
            "label": "LLM 路由决策",
            "latency_ms": 12,
            "status": "completed",
            "detail": "命中 knowledge_chat 工位 → 路由至 deepseek-chat",
        },
        {
            "type": "retrieve",
            "feature": "vector_search",
            "label": "向量检索",
            "latency_ms": 86,
            "status": "completed",
            "detail": "Milvus 召回 2 段相关文档（top_k=4）",
        },
        {
            "type": "llm",
            "feature": "llm_call",
            "label": "LLM 生成",
            "latency_ms": 1340,
            "status": "completed",
            "detail": "deepseek-chat 基于召回文档生成回答",
        },
        {
            "type": "judge",
            "feature": "judge",
            "label": "Judge 五维评分",
            "latency_ms": 540,
            "status": "completed",
            "detail": "综合分 86 · 幻觉率 14%",
        },
    ]
    judge = {
        "overall": 86,
        "hallucination": 14,
        "consistency": 88,
        "completeness": 90,
        "executability": 82,
        "safety": 95,
    }
    event = build_event(
        feature="knowledge_chat",
        task_type="knowledge_chat",
        model="deepseek-chat",
        provider="deepseek",
        input_text="我们的会员系统支持哪些退款方式？退款多久到账？",
        output_text=(
            "根据知识库：本平台支持原路退回和余额退回两种方式，审核通过后 1-3 个工作日到账。"
            "退款需在订单完成后 30 天内发起。"
        ),
        latency_ms=1978,
        token_usage=612,
        trace_id=trace_id,
        retrieved_docs=retrieved_docs,
        trace_steps=trace_steps,
        judge=judge,
        status="completed",
    )
    get_eval_event_store().add(event)
    return {"success": True, "trace_id": trace_id, "event": event.to_dict()}


@router.get("/features")
def list_features():
    """返回 EvalCenter 支持追踪的 AI 功能模块列表。"""
    return [
        {"value": k, "label": v}
        for k, v in FEATURE_LABELS.items()
    ]


@router.get("/feature-stats")
def feature_stats(
    hours: int = Query(24, ge=1, le=2160),
):
    """按功能聚合的流水线概览：调用数 / 幻觉率 / 综合分 / 平均 Token / 平均耗时。

    前端「AI 功能链路概览」卡片的数据源，用于一眼定位哪个功能出问题。
    """
    return get_eval_event_store().stats_by_feature(hours=hours)


@router.get("/trace-panorama/{trace_id}")
def get_trace_panorama(trace_id: str):
    """返回指定 trace_id 的 AI 底座工位全景图。

    列出所有底座能力，并标出本次链路实际调用了哪些、调用几次、耗时多少。
    """
    if not trace_id:
        raise HTTPException(status_code=400, detail="trace_id 不能为空")
    return {
        "trace_id": trace_id,
        "components": get_eval_event_store().get_trace_panorama(trace_id),
    }
