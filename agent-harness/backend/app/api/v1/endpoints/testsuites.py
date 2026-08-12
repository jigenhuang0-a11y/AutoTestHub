"""
测试套件 API（Phase 3 迁移）

提供套件 CRUD、增删用例、执行套件（模拟）等能力。
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

router = APIRouter(prefix="/testsuites", tags=["testsuites"])


class TestSuiteCreate(BaseModel):
    name: str = ""
    description: str = ""
    project: str = ""
    test_case_ids: Any = Field(default_factory=list)
    tags: Any = Field(default_factory=list)
    created_by: str = ""


class AddCasesPayload(BaseModel):
    test_case_ids: list = []


def _dump(v) -> str:
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


@router.get("/")
async def list_suites(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_auth),
):
    store = get_task_store()
    rows, total = store.list_testsuites(page=page, page_size=page_size)
    return {"items": [r.to_dict() for r in rows], "total": total,
            "page": page, "page_size": page_size}


@router.post("/")
async def create_suite(payload: TestSuiteCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    data = payload.model_dump()
    data["test_case_ids"] = _dump(data["test_case_ids"])
    data["tags"] = _dump(data["tags"])
    rec = store.create_testsuite(data)
    return rec.to_dict()


@router.get("/{suite_id}/")
async def get_suite(suite_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_testsuite(suite_id)
    if not rec:
        raise HTTPException(status_code=404, detail="套件不存在")
    return rec.to_dict()


@router.put("/{suite_id}/")
async def update_suite(suite_id: str, payload: TestSuiteCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    if not store.get_testsuite(suite_id):
        raise HTTPException(status_code=404, detail="套件不存在")
    data = {k: v for k, v in payload.model_dump().items()}
    if "test_case_ids" in data:
        data["test_case_ids"] = _dump(data["test_case_ids"])
    if "tags" in data:
        data["tags"] = _dump(data["tags"])
    rec = store.update_testsuite(suite_id, data)
    return rec.to_dict()


@router.delete("/{suite_id}/")
async def delete_suite(suite_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    ok = store.delete_testsuite(suite_id)
    if not ok:
        raise HTTPException(status_code=404, detail="套件不存在")
    return {"ok": True, "deleted": suite_id}


@router.post("/{suite_id}/add-test-cases/")
async def add_cases(suite_id: str, payload: AddCasesPayload, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_testsuite(suite_id)
    if not rec:
        raise HTTPException(status_code=404, detail="套件不存在")
    current = rec.test_case_ids if isinstance(rec.test_case_ids, list) else []
    merged = list(dict.fromkeys(current + payload.test_case_ids))
    rec = store.update_testsuite(suite_id, {"test_case_ids": _dump(merged)})
    return rec.to_dict()


@router.post("/{suite_id}/remove-test-case/")
async def remove_case(suite_id: str, payload: AddCasesPayload, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_testsuite(suite_id)
    if not rec:
        raise HTTPException(status_code=404, detail="套件不存在")
    current = rec.test_case_ids if isinstance(rec.test_case_ids, list) else []
    removed = set(payload.test_case_ids)
    merged = [c for c in current if c not in removed]
    rec = store.update_testsuite(suite_id, {"test_case_ids": _dump(merged)})
    return rec.to_dict()


@router.post("/{suite_id}/execute/")
async def execute_suite(suite_id: str, _: None = Depends(require_auth)):
    """执行套件（模拟）：随机返回通过率。"""
    store = get_task_store()
    rec = store.get_testsuite(suite_id)
    if not rec:
        raise HTTPException(status_code=404, detail="套件不存在")
    ids = rec.test_case_ids if isinstance(rec.test_case_ids, list) else []
    total = len(ids)
    passed = random.randint(0, total) if total else 0
    return {
        "ok": True,
        "suite_id": suite_id,
        "status": "completed",
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": total - passed,
        "summary": f"套件执行完成：{total} 个用例，{passed} 通过",
    }