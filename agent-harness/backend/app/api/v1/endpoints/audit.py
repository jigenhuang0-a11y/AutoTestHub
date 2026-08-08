"""
审计 API — 为审计大屏提供数据查询接口

端点：
  GET  /audit/stats          — 统计概览
  GET  /audit/safety-trend   — 安全扫描趋势
  GET  /audit/risk-dist      — 风险分布
  GET  /audit/events         — 事件列表
  GET  /audit/events/:id     — 单条事件详情
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from app.core.audit_store import get_audit_store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
async def audit_stats(
    team_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
):
    """审计大屏顶部指标"""
    store = get_audit_store()
    try:
        stats = store.get_stats(team_id=team_id, days=days)
    except Exception as e:
        logger.exception("审计统计查询失败")
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "data": stats}


@router.get("/safety-trend")
async def safety_trend(
    team_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
):
    """安全扫描每日趋势"""
    store = get_audit_store()
    try:
        data = store.get_safety_trend(team_id=team_id, days=days)
    except Exception as e:
        logger.exception("安全趋势查询失败")
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "data": data}


@router.get("/risk-distribution")
async def risk_distribution(
    team_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
):
    """风险等级分布"""
    store = get_audit_store()
    try:
        data = store.get_risk_distribution(team_id=team_id, days=days)
    except Exception as e:
        logger.exception("风险分布查询失败")
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "data": data}


@router.get("/events")
async def audit_events(
    team_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    safety_level: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """审计事件列表"""
    store = get_audit_store()
    try:
        events = store.get_recent_events(team_id=team_id, limit=limit)
        # 如果指定了 event_type 或 safety_level，做内存过滤（简单场景）
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]
        if safety_level:
            events = [e for e in events if e.get("safety_level") == safety_level]
    except Exception as e:
        logger.exception("审计事件查询失败")
        raise HTTPException(status_code=500, detail=str(e))
    return {"success": True, "data": {"events": events, "total": len(events)}}


@router.get("/events/{event_id}")
async def audit_event_detail(event_id: int):
    """单条审计事件详情"""
    store = get_audit_store()
    events = store.query(limit=1)
    # 简单查找
    with store._get_conn() as conn:
        row = conn.execute("SELECT * FROM audit_events WHERE id = ?", (event_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="事件不存在")
    return {"success": True, "data": dict(row)}
