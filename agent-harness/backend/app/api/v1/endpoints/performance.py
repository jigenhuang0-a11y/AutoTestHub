"""
性能测试 API（Phase 3 迁移）

提供性能测试计划 CRUD、运行（模拟）等能力。
"""
import logging
import json
import random

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Optional

from app.api.v1.endpoints.auth import get_current_user as require_auth
from app.core.task_store import get_task_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["performance"])


class PerfPlanCreate(BaseModel):
    name: str = ""
    description: str = ""
    target_url: str = ""
    concurrency: int = 10
    duration: int = 60
    ramp_up: int = 0
    scenario: Any = Field(default_factory=list)
    status: str = "draft"
    creator: str = ""


def _dump(v) -> str:
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


@router.get("/")
async def list_plans(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_auth),
):
    store = get_task_store()
    rows, total = store.list_perf_plans(page=page, page_size=page_size)
    return {"items": [r.to_dict() for r in rows], "total": total,
            "page": page, "page_size": page_size}


@router.post("/")
async def create_plan(payload: PerfPlanCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    data = payload.model_dump()
    data["scenario"] = _dump(data["scenario"])
    rec = store.create_perf_plan(data)
    return rec.to_dict()


# 注意：所有静态 /executions/、/execute/ 路由必须放在 /{pp_id}/ 之前，
# 否则 /executions 会被当成路径参数。
# ── 性能执行（模拟）──
@router.post("/execute/")
async def execute_perf(payload: dict = {}, _: None = Depends(require_auth)):
    """按请求直接执行性能测试（模拟）。"""
    pp_id = (payload or {}).get("plan_id", "")
    total_req = random.randint(1000, 50000)
    return {
        "ok": True,
        "exec_id": f"pe-{random.randint(10000, 99999)}",
        "pp_id": pp_id,
        "status": "completed",
        "total_requests": total_req,
        "rps": round(random.uniform(50, 500), 1),
        "avg_response_time": round(random.uniform(20, 200), 1),
        "p95_response_time": round(random.uniform(100, 500), 1),
        "error_rate": round(random.uniform(0, 5), 2),
        "summary": f"性能测试完成：{total_req} 请求",
    }


@router.get("/executions/")
async def list_perf_executions(_: None = Depends(require_auth)):
    return {"items": [], "total": 0}


@router.get("/executions/{exec_id}/")
async def get_perf_execution(exec_id: str, _: None = Depends(require_auth)):
    raise HTTPException(status_code=404, detail="执行记录不存在")


@router.delete("/executions/{exec_id}/")
async def delete_perf_execution(exec_id: str, _: None = Depends(require_auth)):
    return {"ok": True, "deleted": exec_id}


@router.post("/executions/{exec_id}/stop/")
async def stop_perf_execution(exec_id: str, _: None = Depends(require_auth)):
    return {"ok": True, "exec_id": exec_id, "status": "stopped"}


@router.get("/executions/{exec_id}/metrics/")
async def perf_execution_metrics(exec_id: str, _: None = Depends(require_auth)):
    return {"ok": True, "exec_id": exec_id, "metrics": {
        "rps": [], "avg_response_time": [], "error_rate": []}}


@router.post("/executions/{exec_id}/diagnose/")
async def perf_execution_diagnose(exec_id: str, _: None = Depends(require_auth)):
    return {"ok": True, "exec_id": exec_id, "diagnosis": "模拟诊断：未发现明显瓶颈"}


@router.get("/{pp_id}/")
async def get_plan(pp_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store._get_perf_plan(pp_id)
    if not rec:
        raise HTTPException(status_code=404, detail="计划不存在")
    return rec.to_dict()


@router.delete("/{pp_id}/")
async def delete_plan(pp_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    ok = store.delete_perf_plan(pp_id)
    if not ok:
        raise HTTPException(status_code=404, detail="计划不存在")
    return {"ok": True, "deleted": pp_id}


@router.post("/{pp_id}/run/")
async def run_plan(pp_id: str, _: None = Depends(require_auth)):
    """运行性能测试（模拟）。"""
    store = get_task_store()
    rec = store._get_perf_plan(pp_id)
    if not rec:
        raise HTTPException(status_code=404, detail="计划不存在")
    total_req = random.randint(1000, 50000)
    ok_rate = round(random.uniform(95.0, 99.9), 2)
    return {
        "ok": True,
        "pp_id": pp_id,
        "status": "completed",
        "total_requests": total_req,
        "rps": round(total_req / max(1, rec.duration), 1),
        "avg_response_time": round(random.uniform(20, 200), 1),
        "p95_response_time": round(random.uniform(100, 500), 1),
        "error_rate": round(100 - ok_rate, 2),
        "summary": f"性能测试完成：{total_req} 请求，成功率 {ok_rate}%",
    }


@router.get("/{pp_id}/run-history/")
async def get_perf_plan_executions(pp_id: str, _: None = Depends(require_auth)):
    return {"items": [], "total": 0}


