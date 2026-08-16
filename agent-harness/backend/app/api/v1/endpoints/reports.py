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


import json


@router.get("/")
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_auth),
):
    store = get_task_store()
    rows, total = store.list_executions(page=page, page_size=page_size)
    results = []
    for d in rows:
        results.append({
            "id": d["exec_id"],
            "exec_id": d["exec_id"],
            "title": d.get("summary") or f"执行 {d['exec_id']}",
            "name": d.get("name") or f"执行 {d['exec_id']}",
            "status": d["status"],
            "total_cases": d["total_cases"],
            "passed_cases": d["passed_cases"],
            "failed_cases": d["failed_cases"],
            "skipped_cases": d.get("skipped_cases", 0),
            "trigger_type": d["trigger_type"],
            "created_at": d["created_at"],
            "duration": d["duration"],
        })
    return {"results": results, "count": total, "page": page, "page_size": page_size}


@router.get("/summary/")
async def reports_summary(_: None = Depends(require_auth)):
    """返回报告页体检大屏聚合数据。"""
    store = get_task_store()
    rows, _ = store.list_executions(page=1, page_size=1000)
    total = len(rows)
    if total == 0:
        return {
            "total_executions": 0,
            "total_cases": 0,
            "pass_rate": 0,
            "fail_rate": 0,
            "skip_rate": 0,
            "avg_duration": 0,
            "latest": None,
        }
    total_cases = sum(r["total_cases"] for r in rows)
    passed_cases = sum(r["passed_cases"] for r in rows)
    failed_cases = sum(r["failed_cases"] for r in rows)
    skipped_cases = sum(r.get("skipped_cases", 0) for r in rows)
    avg_duration = sum(float(r["duration"] or 0) for r in rows) / total
    pass_rate = round(passed_cases / total_cases * 100, 2) if total_cases else 0
    fail_rate = round(failed_cases / total_cases * 100, 2) if total_cases else 0
    skip_rate = round(skipped_cases / total_cases * 100, 2) if total_cases else 0
    return {
        "total_executions": total,
        "total_cases": total_cases,
        "pass_rate": pass_rate,
        "fail_rate": fail_rate,
        "skip_rate": skip_rate,
        "avg_duration": round(avg_duration, 2),
        "latest": rows[0],
    }


@router.post("/health/")
async def reports_health(data: dict, _: None = Depends(require_auth)):
    """接收报告ID，返回该报告的体检结论与建议。"""
    report_id = data.get("report_id", "")
    store = get_task_store()
    rec = store.get_execution(report_id)
    if not rec:
        raise HTTPException(status_code=404, detail="报告不存在")
    total = rec["total_cases"] or 1
    passed = rec["passed_cases"]
    failed = rec["failed_cases"]
    skipped = rec.get("skipped_cases", 0)
    pass_rate = round(passed / total * 100, 2)
    fail_rate = round(failed / total * 100, 2)
    skip_rate = round(skipped / total * 100, 2)
    score = 100 - fail_rate * 1.5 - skip_rate * 0.5
    score = max(0, round(score, 2))

    suggestions = []
    if fail_rate > 0:
        suggestions.append(f"失败用例占比 {fail_rate}%，建议优先修复失败场景并补充断言。")
    if skip_rate > 0:
        suggestions.append(f"跳过用例占比 {skip_rate}%，建议检查前置依赖与数据工厂配置。")
    if pass_rate >= 95:
        suggestions.append("当前通过率高，建议持续集成每日构建触发。")
    elif pass_rate >= 80:
        suggestions.append("整体质量良好，建议补充边界条件覆盖。")
    else:
        suggestions.append("整体通过率偏低，建议先跑通主链路再扩展场景。")

    return {
        "report_id": report_id,
        "score": score,
        "grade": "A" if score >= 90 else ("B" if score >= 75 else ("C" if score >= 60 else "D")),
        "pass_rate": pass_rate,
        "fail_rate": fail_rate,
        "skip_rate": skip_rate,
        "duration": rec["duration"],
        "suggestions": suggestions,
    }


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
                    r[k] = json.loads(v)
                except Exception:
                    pass
    d = rec
    return {
        "id": d["exec_id"],
        "exec_id": d["exec_id"],
        "name": d.get("name") or f"执行 {d['exec_id']}",
        "status": d["status"],
        "summary": d["summary"],
        "total_cases": d["total_cases"],
        "passed_cases": d["passed_cases"],
        "failed_cases": d["failed_cases"],
        "skipped_cases": d.get("skipped_cases", 0),
        "duration": d["duration"],
        "created_at": d["created_at"],
        "results": results,
    }