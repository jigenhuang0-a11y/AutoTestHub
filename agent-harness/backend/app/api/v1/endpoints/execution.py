"""
接口测试执行 API（Phase 3 迁移）

提供执行记录 CRUD、触发执行（模拟）、获取执行详情与结果、统计等能力。
执行类接口返回模拟结果，不真正发起 HTTP 请求。
"""
import json
import logging
import random
import time as _t
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.api.v1.endpoints.auth import get_current_user as require_auth
from app.core.task_store import get_task_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/execution", tags=["execution"])


class ExecutePayload(BaseModel):
    test_case_ids: list = []
    trigger_type: str = "manual"
    environment: str = ""
    model_id: str = ""


def _run_simulation(store, test_case_ids: list) -> dict:
    """模拟执行一批用例，写入 executions + execution_results 并返回。"""
    results = []
    passed = failed = 0
    for tc_id in test_case_ids:
        store.get_testcase(tc_id)
        status_code = random.choice([200, 200, 200, 400, 401, 500, 404])
        ok = 200 <= status_code < 400
        cost = round(random.uniform(15, 150), 1)
        res = {
            "test_case_id": tc_id,
            "status": "pass" if ok else "fail",
            "request_time": round(_t.time(), 3),
            "response_time": cost,
            "status_code": status_code,
            "error_message": "" if ok else "模拟断言失败",
            "assertions": [{"type": "status_code", "expected": 200, "actual": status_code, "passed": ok}],
            "response_body": {"code": 0 if ok else status_code},
            "extracted_vars": {},
        }
        results.append(res)
        if ok:
            passed += 1
        else:
            failed += 1
    exec_rec = store.create_execution({
        "trigger_type": "manual",
        "test_case_ids": test_case_ids,
        "total_cases": len(test_case_ids),
        "passed_cases": passed,
        "failed_cases": failed,
        "warning_cases": 0,
        "skipped_cases": 0,
        "status": "completed",
        "duration": int(sum(r["response_time"] for r in results) * 1000),
        "response_time": round(sum(r["response_time"] for r in results) / max(1, len(results)), 2),
        "report_url": "",
        "summary": f"{len(test_case_ids)} 个用例中 {passed} 通过 {failed} 失败",
    })
    store.bulk_create_execution_results(exec_rec.exec_id, results)
    return exec_rec.to_dict()


@router.get("/")
async def list_executions(
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_auth),
):
    store = get_task_store()
    rows, total = store.list_executions(
        page=page, page_size=page_size, status=status or None)
    return {"results": rows, "count": total,
            "page": page, "page_size": page_size}


@router.post("/")
@router.post("/execute/")
async def execute(payload: ExecutePayload, _: None = Depends(require_auth)):
    store = get_task_store()
    if not payload.test_case_ids:
        raise HTTPException(status_code=400, detail="请选择至少一条用例")
    exec_dict = _run_simulation(store, payload.test_case_ids)
    # 尝试用真实 LLM 生成执行总结（失败静默降级）
    try:
        from app.core.llm_helper import generate_text
        d = exec_dict
        prompt = f"请用 2-3 句话总结这次接口测试执行：共 {d['total_cases']} 条，通过 {d['passed_cases']}，失败 {d['failed_cases']}。"
        ai_summary = await generate_text(prompt, model_id=payload.model_id or None, temperature=0.4)
        if ai_summary:
            store.update_execution(d["exec_id"], {"summary": ai_summary})
            exec_dict = store.get_execution(d["exec_id"]).to_dict()
            exec_dict["ai_enhanced"] = True
    except Exception as e:
        logger.warning(f"[execution] AI 总结不可用，保留规则总结: {e}")
        exec_dict["ai_enhanced"] = False
    return {"ok": True, "execution": exec_dict}


@router.get("/{exec_id}/")
async def get_execution(exec_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_execution(exec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    results = store.list_execution_results(exec_id)
    for r in results:
        for k in ("assertions", "response_body", "extracted_vars"):
            v = r.get(k)
            if isinstance(v, str):
                try:
                    r[k] = json.loads(v)
                except Exception:
                    pass
    return {**rec, "results": results}


@router.post("/{exec_id}/rerun/")
async def rerun(exec_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_execution(exec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    ids = list({r.get("case_id") for r in store.list_execution_results(exec_id) if r.get("case_id")})
    if not ids:
        raise HTTPException(status_code=400, detail="无可重跑的用例")
    new_rec = _run_simulation(store, ids)
    return {"ok": True, "execution": new_rec}


@router.post("/{exec_id}/export_report/")
async def export_report(exec_id: str, _: None = Depends(require_auth)):
    """导出执行报告（模拟 HTML 文本）。"""
    from fastapi.responses import HTMLResponse
    store = get_task_store()
    rec = store.get_execution(exec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    d = rec.to_dict()
    html = (f"<html><body><h1>测试报告 {d['exec_id']}</h1>"
            f"<p>状态：{d['status']}</p>"
            f"<p>通过：{d['passed_cases']} / 失败：{d['failed_cases']}</p>"
            f"<p>{d['summary']}</p></body></html>")
    return HTMLResponse(content=html)


@router.delete("/{exec_id}/")
async def delete_execution(exec_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    ok = store.delete_execution(exec_id)
    if not ok:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return {"ok": True, "deleted": exec_id}


@router.get("/stats/summary/")
async def execution_stats(_: None = Depends(require_auth)):
    store = get_task_store()
    return store.get_execution_stats()
