import logging
"""
测试报告 / 执行历史 API（Phase 3 迁移）

报告基于 execution 记录生成；历史页直接复用 execution 列表。
前端 ReportView 期望 { results, count } 结构，这里兼容返回。
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.endpoints.auth import get_current_user as require_auth
from app.core.task_store import get_task_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/")
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_auth),
):
    store = get_task_store()
    rows, total = store.list_executions(page=page, page_size=page_size)
    results = []
    for r in rows:
        d = r.to_dict()
        results.append({
            "id": d["exec_id"],
            "exec_id": d["exec_id"],
            "title": d.get("summary") or f"执行 {d['exec_id']}",
            "status": d["status"],
            "total_cases": d["total_cases"],
            "passed_cases": d["passed_cases"],
            "failed_cases": d["failed_cases"],
            "trigger_type": d["trigger_type"],
            "created_at": d["created_at"],
            "duration": d["duration"],
        })
    return {"results": results, "count": total, "page": page, "page_size": page_size}


@router.get("/{report_id}/")
async def get_report(report_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_execution(report_id)
    if not rec:
        raise HTTPException(status_code=404, detail="报告不存在")
    results = store.list_execution_results(report_id)
    for r in results:
        for k in ("assertions", "response_body", "extracted_vars"):
            v = r.get(k)
            if isinstance(v, str):
                try:
                    import json
                    r[k] = json.loads(v)
                except Exception:
                    pass
    d = rec.to_dict()
    return {
        "id": d["exec_id"],
        "exec_id": d["exec_id"],
        "status": d["status"],
        "summary": d["summary"],
        "total_cases": d["total_cases"],
        "passed_cases": d["passed_cases"],
        "failed_cases": d["failed_cases"],
        "duration": d["duration"],
        "response_time": d["response_time"],
        "created_at": d["created_at"],
        "test_case_ids": d["test_case_ids"],
        "results": results,
    }