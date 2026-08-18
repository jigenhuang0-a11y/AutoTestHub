import logging
"""
测试报告 / 执行历史 API（Phase 3 迁移）

报告基于 execution 记录生成；历史页直接复用 execution 列表。
前端 ReportView 期望 { results, count } 结构，这里兼容返回。
"""
from datetime import datetime

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


@router.post("/generate/")
async def generate_report(_: None = Depends(require_auth)):
    """读取当前全平台测试执行进度，汇总生成一条测试报告。"""
    store = get_task_store()
    with store._get_conn() as conn:
        # 1) 汇总 Web/UI 自动化执行
        web_rows = conn.execute(
            "SELECT status, duration_ms FROM web_executions"
        ).fetchall()
        web_total = len(web_rows)
        web_passed = sum(1 for r in web_rows if r["status"] in ("passed", "completed"))
        web_failed = sum(1 for r in web_rows if r["status"] in ("failed", "error"))
        web_skipped = sum(1 for r in web_rows if r["status"] == "skipped")

        # 2) 汇总性能测试执行
        perf_rows = conn.execute(
            "SELECT status, duration, total_requests, failures FROM perf_executions"
        ).fetchall()
        perf_total = len(perf_rows)
        perf_passed = sum(1 for r in perf_rows if r["status"] in ("passed", "completed"))
        perf_failed = sum(1 for r in perf_rows if r["status"] in ("failed", "error"))
        perf_skipped = 0

        # 3) 汇总接口测试用例（以 testcases 表中 status=active 视为待执行/已覆盖）
        api_rows = conn.execute("SELECT status FROM testcases").fetchall()
        api_total = len(api_rows)
        api_passed = sum(1 for r in api_rows if r["status"] in ("active", "passed"))
        api_failed = sum(1 for r in api_rows if r["status"] == "failed")
        api_skipped = sum(1 for r in api_rows if r["status"] == "deprecated")

        # 4) 汇总测试套件
        suite_rows = conn.execute("SELECT last_execution_status FROM testsuites").fetchall()
        suite_total = len(suite_rows)
        suite_passed = sum(1 for r in suite_rows if r["last_execution_status"] == "passed")
        suite_failed = sum(1 for r in suite_rows if r["last_execution_status"] == "failed")
        suite_skipped = sum(1 for r in suite_rows if r["last_execution_status"] in ("skipped", "unexecuted"))

    total_cases = web_total + perf_total + api_total + suite_total
    passed_cases = web_passed + perf_passed + api_passed + suite_passed
    failed_cases = web_failed + perf_failed + api_failed + suite_failed
    skipped_cases = web_skipped + perf_skipped + api_skipped + suite_skipped

    web_dur = sum(r["duration_ms"] or 0 for r in web_rows) / 1000
    perf_dur = sum(float(r["duration"] or 0) for r in perf_rows)
    duration = round(web_dur + perf_dur, 2)

    pass_rate = round(passed_cases / total_cases * 100, 2) if total_cases else 0
    fail_rate = round(failed_cases / total_cases * 100, 2) if total_cases else 0
    skip_rate = round(skipped_cases / total_cases * 100, 2) if total_cases else 0

    summary = (
        f"全平台汇总：UI {web_total} 条、性能 {perf_total} 条、"
        f"接口 {api_total} 条、套件 {suite_total} 条；"
        f"通过 {pass_rate}%，失败 {fail_rate}%，跳过 {skip_rate}%。"
    )

    results = []
    for idx, r in enumerate(web_rows, 1):
        results.append({
            "case_id": f"web-{idx:04d}",
            "case_title": f"Web 自动化执行 #{idx}",
            "status": "passed" if r["status"] in ("passed", "completed") else ("failed" if r["status"] in ("failed", "error") else r["status"]),
            "duration_ms": r["duration_ms"] or 0,
            "error_message": "",
        })
    for idx, r in enumerate(perf_rows, 1):
        results.append({
            "case_id": f"perf-{idx:04d}",
            "case_title": f"性能测试执行 #{idx}",
            "status": "passed" if r["status"] in ("passed", "completed") else ("failed" if r["status"] in ("failed", "error") else r["status"]),
            "duration_ms": int((r["duration"] or 0) * 1000),
            "error_message": f"失败 {r['failures'] or 0} / 总请求 {r['total_requests'] or 0}" if r["status"] in ("failed", "error") else "",
        })

    created = store.create_execution({
        "name": f"全平台测试报告 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "status": "completed",
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "skipped_cases": skipped_cases,
        "duration": duration,
        "trigger_type": "manual",
        "summary": summary,
        "results": results,
    })
    return {
        "exec_id": created["exec_id"],
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "skipped_cases": skipped_cases,
        "pass_rate": pass_rate,
        "duration": duration,
        "summary": summary,
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