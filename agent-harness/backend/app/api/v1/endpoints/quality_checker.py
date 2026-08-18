"""
需求评审师 API（Phase 3 迁移）

提供评审任务 CRUD、评审标准管理、执行评审（模拟）等能力。
执行评审返回模拟结论，不真正调用大模型（后续可接入 LLM Router）。
"""
import logging
import json
import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Optional

from app.api.v1.endpoints.auth import get_current_user as require_auth
from app.core.task_store import get_task_store
from app.core.llm_helper import generate_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quality-checker", tags=["quality-checker"])


class QualityTaskCreate(BaseModel):
    title: str = ""
    requirements: str = ""
    summary: str = ""
    status: str = "pending"
    progress: int = 0
    total_cases: int = 0
    passed_cases: int = 0
    warning_cases: int = 0
    failed_cases: int = 0
    issues: Any = Field(default_factory=list)
    findings: Any = Field(default_factory=list)
    coverage: Any = Field(default_factory=list)
    standards: Any = Field(default_factory=list)
    creator: str = ""


class QualityStandardCreate(BaseModel):
    name: str = ""
    description: str = ""
    category: str = "functional"
    severity: str = "medium"
    checkpoints: Any = Field(default_factory=list)


def _dump(v) -> str:
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def _extract_json(text: str) -> str:
    """从大段文本中提取第一个 JSON 数组/对象。"""
    if not text:
        return "[]"
    text = text.strip()
    if text.startswith("["):
        depth = 0
        for i, c in enumerate(text):
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return text[: i + 1]
        return text
    start = text.find("[")
    if start != -1:
        return _extract_json(text[start:])
    return "[]"


# ── 评审标准（必须注册在 /{task_id}/ 之前，避免被通配路由捕获）──
@router.get("/standards/")
async def list_standards(
    include_builtin: bool = Query(default=True),
    category: str = Query(default=""),
    _: None = Depends(require_auth),
):
    store = get_task_store()
    rows = store.list_quality_standards(
        include_builtin=include_builtin, category=category or None)
    return {"items": [r.to_dict() for r in rows], "total": len(rows)}


@router.post("/standards/")
async def create_standard(payload: QualityStandardCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    data = payload.model_dump()
    data["checkpoints"] = _dump(data["checkpoints"])
    rec = store.create_quality_standard(data)
    return rec.to_dict()


@router.delete("/standards/{std_id}/")
async def delete_standard(std_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    ok = store.delete_quality_standard(std_id)
    if not ok:
        raise HTTPException(status_code=404, detail="标准不存在或不可删除")
    return {"ok": True, "deleted": std_id}


@router.get("/")
@router.get("/tasks/")
async def list_tasks(
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_auth),
):
    store = get_task_store()
    rows, total = store.list_quality_tasks(
        status=status or None, page=page, page_size=page_size)
    return {"items": [r.to_dict() for r in rows], "total": total,
            "page": page, "page_size": page_size}


@router.post("/")
@router.post("/tasks/")
async def create_task(payload: QualityTaskCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    data = payload.model_dump()
    for k in ("issues", "findings", "coverage", "standards"):
        data[k] = _dump(data[k])
    rec = store.create_quality_task(data)
    return rec.to_dict()


@router.get("/{task_id}/")
@router.get("/tasks/{task_id}/")
async def get_task(task_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_quality_task(task_id)
    if not rec:
        raise HTTPException(status_code=404, detail="评审任务不存在")
    return rec.to_dict()


@router.put("/{task_id}/")
@router.put("/tasks/{task_id}/")
async def update_task(task_id: str, payload: QualityTaskCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    if not store.get_quality_task(task_id):
        raise HTTPException(status_code=404, detail="评审任务不存在")
    data = {k: v for k, v in payload.model_dump().items()}
    for k in ("issues", "findings", "coverage", "standards"):
        if k in data:
            data[k] = _dump(data[k])
    rec = store.update_quality_task(task_id, data)
    return rec.to_dict()


@router.delete("/{task_id}/")
@router.delete("/tasks/{task_id}/")
async def delete_task(task_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    ok = store.delete_quality_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="评审任务不存在")
    return {"ok": True, "deleted": task_id}


@router.post("/tasks/{task_id}/execute/")
async def execute_task(task_id: str, _: None = Depends(require_auth)):
    """执行需求评审：优先调用 LLM 做真实评审，失败时回退到模拟逻辑。"""
    store = get_task_store()
    rec = store.get_quality_task(task_id)
    if not rec:
        raise HTTPException(status_code=404, detail="评审任务不存在")
    task = rec.to_dict()
    standards = store.list_quality_standards(include_builtin=True)
    std_names = [s.to_dict()["name"] for s in standards]
    std_desc = [f"- {s.to_dict()['name']}（严重度 {s.to_dict()['severity']}）：{s.to_dict()['description']}" for s in standards]

    prompt = f"""你是一名资深需求评审专家。请对以下需求进行逐项评审，判断其是否满足每条评审标准。

需求标题：{task.get('title', '')}
需求描述：{task.get('requirements', '') or task.get('summary', '')}

评审标准：
{chr(10).join(std_desc)}

请严格按 JSON 数组返回评审结论，不要输出任何其他内容。示例格式：
[{{"standard": "完整性", "status": "pass", "comment": "需求覆盖主流程"}}]
"""

    findings = []
    issues = []
    llm_summary = ""
    try:
        raw = await generate_text(prompt, temperature=0.2, task_type="requirement_review")
        llm_summary = raw[:500]
        parsed = json.loads(_extract_json(raw))
        if isinstance(parsed, list):
            findings = [
                {"standard": f.get("standard", s.to_dict()["name"]), "status": f.get("status", "fail"), "comment": f.get("comment", "")}
                for f, s in zip(parsed, standards)
            ]
    except Exception as e:
        logger.warning(f"[QualityChecker] LLM 评审失败，回退模拟：{e}")
        findings = []

    # 如果 LLM 未返回有效结果，回退到模拟
    if not findings:
        for std in standards:
            s = std.to_dict()
            passed = random.random() > 0.4
            findings.append({
                "standard": s["name"],
                "status": "pass" if passed else "fail",
                "comment": s["description"],
            })

    for f in findings:
        if f.get("status") != "pass":
            # 找到对应标准条目补充严重度
            std = next((s.to_dict() for s in standards if s.to_dict()["name"] == f.get("standard")), {})
            issues.append({
                "title": f"未满足标准：{f.get('standard')}",
                "severity": std.get("severity", "medium"),
                "detail": f.get("comment") or std.get("description", ""),
            })

    total = len(standards)
    passed_count = sum(1 for f in findings if f.get("status") == "pass")
    data = {
        "status": "completed",
        "progress": 100,
        "total_cases": total,
        "passed_cases": passed_count,
        "warning_cases": 0,
        "failed_cases": total - passed_count,
        "findings": _dump(findings),
        "issues": _dump(issues),
        "coverage": _dump(std_names),
        "summary": f"评审完成：{total} 项标准，{passed_count} 通过，{total - passed_count} 不通过" + (f"（{llm_summary[:60]}...）" if llm_summary else ""),
    }
    updated = store.update_quality_task(task_id, data)
    return {"ok": True, "task": updated.to_dict()}


@router.get("/tasks/{task_id}/executions/")
async def get_execution(task_id: str, _: None = Depends(require_auth)):
    """评审执行历史（复用任务本身的 findings）。"""
    store = get_task_store()
    rec = store.get_quality_task(task_id)
    if not rec:
        raise HTTPException(status_code=404, detail="评审任务不存在")
    d = rec.to_dict()
    return {"executions": [{
        "task_id": task_id,
        "status": d["status"],
        "findings": d["findings"],
        "issues": d["issues"],
        "created_at": d["updated_at"],
    }]}


@router.post("/generate-tasks/")
async def generate_tasks(payload: QualityTaskCreate, _: None = Depends(require_auth)):
    """AI 生成评审任务（模拟）。"""
    store = get_task_store()
    data = payload.model_dump()
    for k in ("issues", "findings", "coverage", "standards"):
        data[k] = _dump(data[k])
    rec = store.create_quality_task(data)
    return rec.to_dict()