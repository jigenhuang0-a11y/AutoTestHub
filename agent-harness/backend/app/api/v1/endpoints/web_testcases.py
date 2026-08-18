"""
Web/UI 自动化用例 API（Phase 3 迁移）

提供 Web 用例 CRUD、批量保存（来自录制）等能力。执行类接口返回模拟结果。
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

router = APIRouter(prefix="/web-testcases", tags=["web-testcases"])


class WebTestCaseCreate(BaseModel):
    project: str = ""
    module: str = ""
    title: str = ""
    description: str = ""
    page_url: str = ""
    steps: Any = Field(default_factory=list)
    assertion_rules: Any = Field(default_factory=list)
    priority: str = "P2"
    tags: Any = Field(default_factory=list)
    status: str = "draft"
    creator: str = ""


def _dump(v) -> str:
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


@router.get("/")
async def list_web_testcases(
    project: str = Query(default=""),
    module: str = Query(default=""),
    engine: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_auth),
):
    store = get_task_store()
    # 兼容前端查询参数：优先使用 engine/status/keyword
    rows, total = store.list_web_testcases(
        page=page,
        page_size=page_size,
        engine=engine or None,
        status=status or None,
        keyword=keyword or None,
    )
    return {"results": rows, "count": total, "page": page, "page_size": page_size}


@router.post("/")
async def create_web_testcase(payload: WebTestCaseCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    data = payload.model_dump()
    # 前端字段 assertions 与后端存储 assertion_rules 兼容
    if "assertions" in data:
        data["assertion_rules"] = data.pop("assertions")
    data["steps"] = _dump(data["steps"])
    data["assertion_rules"] = _dump(data.get("assertion_rules", []))
    data["tags"] = _dump(data["tags"])
    rec = store.create_web_testcase(data)
    return rec


@router.post("/batch/")
async def batch_create(payload: dict = {}, _: None = Depends(require_auth)):
    store = get_task_store()
    items = payload.get("items", [])
    created = []
    for it in items:
        it = dict(it)
        if "assertions" in it:
            it["assertion_rules"] = it.pop("assertions")
        it["steps"] = _dump(it.get("steps", []))
        it["assertion_rules"] = _dump(it.get("assertion_rules", []))
        it["tags"] = _dump(it.get("tags", []))
        created.append(store.create_web_testcase(it))
    return {"ok": True, "total": len(created), "items": created}


# 注意：所有静态 /executions/ 路由必须放在 /{wtc_id}/ 之前，
# 否则 /executions 会被当成路径参数。
@router.get("/executions/")
async def list_web_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    test_case: Optional[str] = Query(None),
    _: None = Depends(require_auth),
):
    """获取 Web 测试执行历史（分页）。数据来自 TaskStore 的 web_executions 表。"""
    try:
        store = get_task_store()
        rows, total = store.list_web_executions(
            status=status, keyword=keyword, test_case=test_case, page=page, page_size=page_size
        )
        return {
            "results": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as e:
        logger.error(f"获取 Web 执行记录失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取执行记录失败: {str(e)}")


@router.post("/executions/")
async def batch_delete_web_executions(payload: dict = {}, _: None = Depends(require_auth)):
    return {"ok": True, "deleted": 0}


@router.get("/executions/{exec_id}/")
async def get_web_execution(exec_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_web_execution(exec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return rec


@router.delete("/executions/{exec_id}/")
async def delete_web_execution(exec_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    store.delete_web_execution(exec_id)
    return {"ok": True, "deleted": exec_id}


@router.post("/executions/{exec_id}/run/")
async def rerun_web_execution(exec_id: str, _: None = Depends(require_auth)):
    return {"ok": True, "exec_id": exec_id, "status": "pending"}


@router.get("/{wtc_id}/")
async def get_web_testcase(wtc_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_web_testcase(wtc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="用例不存在")
    return rec


@router.patch("/{wtc_id}/")
async def patch_web_testcase(wtc_id: str, payload: WebTestCaseCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    if not store.get_web_testcase(wtc_id):
        raise HTTPException(status_code=404, detail="用例不存在")
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "assertions" in data:
        data["assertion_rules"] = data.pop("assertions")
    if "steps" in data:
        data["steps"] = _dump(data["steps"])
    if "assertion_rules" in data:
        data["assertion_rules"] = _dump(data["assertion_rules"])
    if "tags" in data:
        data["tags"] = _dump(data["tags"])
    rec = store.update_web_testcase(wtc_id, data)
    return rec


@router.delete("/{wtc_id}/")
async def delete_web_testcase(wtc_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    ok = store.delete_web_testcase(wtc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用例不存在")
    return {"ok": True, "deleted": wtc_id}


@router.post("/{wtc_id}/run/")
async def run_web_testcase(wtc_id: str, _: None = Depends(require_auth)):
    """执行 Web 用例（模拟）。"""
    return {
        "ok": True,
        "wtc_id": wtc_id,
        "status": random.choice(["pass", "pass", "fail"]),
        "steps_executed": random.randint(1, 8),
        "screenshot": "",
        "duration": random.randint(500, 3000),
    }


@router.post("/debug/")
async def debug_temp(payload: dict = {}, _: None = Depends(require_auth)):
    return {"ok": True, "status_code": 200, "body": {"message": "mock web debug"}}


@router.get("/{wtc_id}/run-history/")
async def get_web_executions(wtc_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rows, total = store.list_web_executions(test_case=wtc_id)
    return {"items": rows, "total": total}
