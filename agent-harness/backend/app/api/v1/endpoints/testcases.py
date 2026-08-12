"""
接口测试用例 API（Phase 3 迁移）

提供测试用例 CRUD、调试、导入 cURL、AI 解析接口、AI 生成用例等能力。
调试/执行类接口返回模拟结果，不真正发起 HTTP 请求（后续可接入执行引擎）。
"""
import json
import logging
import random
import time as _t
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Optional

from app.api.v1.endpoints.auth import get_current_user as require_auth
from app.core.task_store import get_task_store

logger = logging.getLogger(__name__)


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

router = APIRouter(prefix="/testcases", tags=["testcases"])


# ── 请求体模型 ──
class TestCaseCreate(BaseModel):
    project: str = ""
    module: str = ""
    title: str = ""
    description: str = ""
    method: str = "GET"
    api_endpoint: str = ""
    headers: Any = Field(default_factory=dict)
    request_body: str = ""
    expected_response: str = ""
    assertion_rules: Any = Field(default_factory=list)
    extract_rules: Any = Field(default_factory=list)
    global_vars: Any = Field(default_factory=dict)
    context_vars: Any = Field(default_factory=dict)
    priority: str = "P2"
    tags: Any = Field(default_factory=list)
    status: str = "draft"
    creator: str = ""


class TestCaseUpdate(BaseModel):
    project: Optional[str] = None
    module: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    method: Optional[str] = None
    api_endpoint: Optional[str] = None
    headers: Optional[Any] = None
    request_body: Optional[str] = None
    expected_response: Optional[str] = None
    assertion_rules: Optional[Any] = None
    extract_rules: Optional[Any] = None
    global_vars: Optional[Any] = None
    context_vars: Optional[Any] = None
    priority: Optional[str] = None
    tags: Optional[Any] = None
    status: Optional[str] = None
    creator: Optional[str] = None


class DebugPayload(BaseModel):
    method: str = "GET"
    url: str = ""
    headers: Any = Field(default_factory=dict)
    body: str = ""
    timeout: int = 10
    model_id: str = ""


class AIGeneratePayload(BaseModel):
    requirement: str = ""
    project: str = ""
    count: int = 5
    model_id: str = ""


class AIParsePayload(BaseModel):
    text: str = ""
    format: str = "openapi"  # openapi / curl / markdown
    # 前端「AI 一键解析接口」实际提交的字段
    api_url: str = ""
    method: str = ""
    response_json: str = ""
    request_body: str = ""
    model_id: str = ""


class ImportCurlPayload(BaseModel):
    curl: str = ""


# ── 辅助：把任意对象序列化为 TEXT 列 ──
def _dump(v) -> str:
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


@router.get("/")
async def list_testcases(
    project: str = Query(default=""),
    module: str = Query(default=""),
    status: str = Query(default=""),
    priority: str = Query(default=""),
    keyword: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_auth),
):
    store = get_task_store()
    rows, total = store.list_testcases(
        project=project or None, module=module or None, status=status or None,
        priority=priority or None, keyword=keyword or None, page=page, page_size=page_size,
    )
    return {"items": [r.to_dict() for r in rows], "total": total,
            "page": page, "page_size": page_size}


@router.post("/")
async def create_testcase(payload: TestCaseCreate, _: None = Depends(require_auth)):
    store = get_task_store()
    data = payload.model_dump()
    data["headers"] = _dump(data["headers"])
    data["assertion_rules"] = _dump(data["assertion_rules"])
    data["extract_rules"] = _dump(data["extract_rules"])
    data["global_vars"] = _dump(data["global_vars"])
    data["context_vars"] = _dump(data["context_vars"])
    data["tags"] = _dump(data["tags"])
    rec = store.create_testcase(data)
    return rec.to_dict()


@router.get("/{tc_id}/")
async def get_testcase(tc_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_testcase(tc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="用例不存在")
    return rec.to_dict()


@router.put("/{tc_id}/")
@router.patch("/{tc_id}/")
async def update_testcase(tc_id: str, payload: TestCaseUpdate, _: None = Depends(require_auth)):
    store = get_task_store()
    if not store.get_testcase(tc_id):
        raise HTTPException(status_code=404, detail="用例不存在")
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "headers" in data:
        data["headers"] = _dump(data["headers"])
    if "assertion_rules" in data:
        data["assertion_rules"] = _dump(data["assertion_rules"])
    if "extract_rules" in data:
        data["extract_rules"] = _dump(data["extract_rules"])
    if "global_vars" in data:
        data["global_vars"] = _dump(data["global_vars"])
    if "context_vars" in data:
        data["context_vars"] = _dump(data["context_vars"])
    if "tags" in data:
        data["tags"] = _dump(data["tags"])
    rec = store.update_testcase(tc_id, data)
    return rec.to_dict()


@router.post("/{tc_id}/duplicate/")
async def duplicate_testcase(tc_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_testcase(tc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="用例不存在")
    d = rec.to_dict()
    d.pop("tc_id", None)
    d.pop("id", None)
    d["title"] = d.get("title", "") + " (副本)"
    d["status"] = "draft"
    new_rec = store.create_testcase(d)
    return new_rec.to_dict()


@router.delete("/{tc_id}/")
async def delete_testcase(tc_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    ok = store.delete_testcase(tc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用例不存在")
    return {"ok": True, "deleted": tc_id}


@router.delete("/")
async def batch_delete_testcases(ids: list[str] = [], _: None = Depends(require_auth)):
    store = get_task_store()
    deleted = 0
    for tc_id in ids:
        if store.delete_testcase(tc_id):
            deleted += 1
    return {"ok": True, "deleted": deleted}


@router.post("/{tc_id}/debug/")
async def debug_testcase(tc_id: str, _: None = Depends(require_auth)):
    """调试单个用例（返回模拟执行结果）。"""
    store = get_task_store()
    rec = store.get_testcase(tc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="用例不存在")
    started = _t.time()
    status_code = random.choice([200, 200, 200, 400, 401, 500])
    ok = 200 <= status_code < 400
    cost = round(random.uniform(20, 120), 1)
    result = {
        "test_case_id": tc_id,
        "status": "pass" if ok else "fail",
        "request_time": round(_t.time() - started, 3),
        "response_time": cost,
        "status_code": status_code,
        "error_message": "" if ok else "模拟响应状态码异常",
        "assertions": [
            {"type": "status_code", "expected": 200, "actual": status_code,
             "passed": 200 <= status_code < 400}
        ],
        "response_body": {"code": 0 if ok else status_code, "message": "mock response"},
        "extracted_vars": {},
    }
    return {"ok": True, "execution_results": [result], "passed_count": 1 if ok else 0,
            "failed_count": 0 if ok else 1}


@router.post("/debug-temp/")
async def debug_temp(payload: DebugPayload, _: None = Depends(require_auth)):
    """直接调试一段请求（不落库）。真实 LLM 不可用时返回规则化 mock 结果。"""
    started = _t.time()
    try:
        from app.core.llm_helper import generate_text
        prompt = f"请用一句话模拟以下 HTTP 请求的响应结果（只返回 JSON）：\n{payload.method} {payload.url}\n{payload.body or ''}"
        note = await generate_text(prompt, model_id=payload.model_id or None, temperature=0.3)
    except Exception as e:
        logger.warning(f"[testcases] debug LLM 不可用，mock: {e}")
        note = None
    status_code = 200 if note else random.choice([200, 200, 301, 400, 404, 500])
    cost = round(random.uniform(15, 200), 1)
    body = {"code": 0, "message": (note or "mock response")}
    return {
        "ok": True,
        "status_code": status_code,
        "response_time": cost,
        "request_time": round(_t.time() - started, 3),
        "headers": {"content-type": "application/json"},
        "body": body,
        "response_size": len(json.dumps(body, ensure_ascii=False)),
        "ai_enhanced": bool(note),
    }


@router.post("/ai-generate/")
async def ai_generate(payload: AIGeneratePayload, _: None = Depends(require_auth)):
    """AI 生成接口测试用例（真实 LLM，失败降级 mock 并落库）。"""
    store = get_task_store()
    count = max(1, min(payload.count, 20))
    prompt = f"""你是接口测试专家。请为以下需求生成 {count} 条接口测试用例，以 JSON 数组返回，
每条包含：title(用例标题), method(HTTP方法), api_endpoint(路径), request_body(示例请求体字符串),
expected_response(示例响应字符串), assertion_rules(断言数组，元素为 {{type,expected}}), priority(P0/P1/P2)。
需求：{payload.requirement}
项目：{payload.project or '默认项目'}"""
    try:
        from app.core.llm_helper import generate_text
        raw = await generate_text(prompt, model_id=payload.model_id or None, temperature=0.7)
        cases = _parse_llm_testcases(raw, payload, count)
        used_llm = True
    except Exception as e:
        logger.warning(f"[testcases] AI 生成失败，降级 mock: {e}")
        cases = [_mock_testcase(payload, i) for i in range(count)]
        used_llm = False

    created = []
    for s in cases:
        s["headers"] = _dump(s.get("headers", {"Content-Type": "application/json"}))
        s["assertion_rules"] = _dump(s.get("assertion_rules", [{"type": "status_code", "expected": 200}]))
        s["extract_rules"] = _dump(s.get("extract_rules", []))
        s["tags"] = _dump(s.get("tags", ["ai-generated"]))
        s["status"] = "draft"
        s["creator"] = "ai"
        created.append(store.create_testcase(s).to_dict())
    return {"ok": True, "test_cases": created, "total": len(created), "ai_enhanced": used_llm}


@router.post("/ai-parse-interface/")
async def ai_parse_interface(payload: AIParsePayload, _: None = Depends(require_auth)):
    """AI 解析接口定义（openapi/curl/markdown）为用例草稿。"""
    text = (payload.text or "").strip()
    if not text:
        # 兼容前端「AI 一键解析接口」的字段
        parts = []
        if payload.method:
            parts.append(f"请求方法：{payload.method}")
        if payload.api_url:
            parts.append(f"请求地址：{payload.api_url}")
        if payload.request_body:
            parts.append(f"请求体：\n{payload.request_body}")
        if payload.response_json:
            parts.append(f"响应示例：\n{payload.response_json}")
        text = "\n".join(parts)
    if not text:
        raise HTTPException(status_code=400, detail="解析内容不能为空")
    try:
        from app.core.llm_helper import generate_text
        prompt = f"解析下面的接口定义，提取 method、api_endpoint、请求头、请求体示例，以 JSON 返回：\n{text[:2000]}"
        raw = await generate_text(prompt, model_id=payload.model_id or None, temperature=0.2)
        parsed = _parse_interface_raw(raw)
        used_llm = True
    except Exception as e:
        logger.warning(f"[testcases] AI 解析失败，降级规则解析: {e}")
        parsed = _rule_based_parse(text, payload.format)
        used_llm = False
    return {"ok": True, "parsed": parsed, "format": payload.format, "ai_enhanced": used_llm}


def _mock_testcase(payload: AIGeneratePayload, i: int) -> dict:
    ep = f"/api/v1/{payload.project or 'resource'}/{i+1}"
    return {
        "project": payload.project or "AI生成",
        "module": "generated",
        "title": f"{payload.requirement[:20] or '用例'} #{i+1}",
        "description": payload.requirement,
        "method": "POST",
        "api_endpoint": ep,
        "request_body": "{}",
        "expected_response": '{"code": 0}',
        "assertion_rules": [{"type": "status_code", "expected": 200}],
        "extract_rules": [],
        "priority": "P2",
        "tags": ["ai-generated"],
    }


def _parse_llm_testcases(raw: str, payload: AIGeneratePayload, count: int) -> list:
    import re
    text = (raw or "").strip()
    try:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            arr = json.loads(text[start:end + 1])
            if isinstance(arr, list) and arr:
                out = []
                for it in arr[:count]:
                    if not isinstance(it, dict):
                        continue
                    out.append({
                        "project": payload.project or "AI生成",
                        "module": "generated",
                        "title": str(it.get("title", "用例")),
                        "description": payload.requirement,
                        "method": str(it.get("method", "POST")).upper(),
                        "api_endpoint": str(it.get("api_endpoint", "")),
                        "request_body": str(it.get("request_body", "{}")),
                        "expected_response": str(it.get("expected_response", '{"code":0}')),
                        "assertion_rules": it.get("assertion_rules", [{"type": "status_code", "expected": 200}]),
                        "extract_rules": [],
                        "priority": it.get("priority", "P2"),
                        "tags": ["ai-generated"],
                    })
                if out:
                    return out
    except Exception as e:
        logger.warning(f"[testcases] 解析 LLM 用例失败: {e}")
    return [_mock_testcase(payload, i) for i in range(count)]


def _rule_based_parse(text: str, fmt: str) -> dict:
    lines = text.splitlines()
    method, url = "GET", ""
    if fmt == "curl" or text.startswith("curl"):
        for tok in text.split():
            if tok.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                method = tok.upper()
            elif tok.startswith("http"):
                url = tok
    elif lines:
        first = lines[0]
        if " " in first:
            method = first.split()[0].upper()
            parts = first.split()
            if len(parts) > 1:
                url = parts[1]
    return {
        "method": method,
        "api_endpoint": url,
        "headers": {"Content-Type": "application/json"},
        "request_body": "",
        "assertion_rules": [{"type": "status_code", "expected": 200}],
    }


def _parse_interface_raw(raw: str) -> dict:
    import re
    text = (raw or "").strip()
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            obj = json.loads(text[start:end + 1])
            obj.setdefault("headers", {"Content-Type": "application/json"})
            obj.setdefault("assertion_rules", [{"type": "status_code", "expected": 200}])
            return obj
    except Exception:
        pass
    return _rule_based_parse(text, "text")


@router.post("/import-curl/")
async def import_curl(payload: ImportCurlPayload, _: None = Depends(require_auth)):
    """从 cURL 导入为用例。"""
    curl = (payload.curl or "").strip()
    if not curl:
        raise HTTPException(status_code=400, detail="cURL 内容不能为空")
    parsed = await ai_parse_interface(AIParsePayload(text=curl, format="curl"), _)
    return {
        "ok": True,
        "test_case": {
            "method": parsed["parsed"]["method"],
            "api_endpoint": parsed["parsed"]["api_endpoint"],
            "headers": parsed["parsed"]["headers"],
            "request_body": "",
            "assertion_rules": parsed["parsed"]["assertion_rules"],
        },
    }


@router.get("/export/curl/")
async def export_curl(tc_id: str = Query(default=""), _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_testcase(tc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="用例不存在")
    d = rec.to_dict()
    header_str = " ".join(f"-H '{k}: {v}'" for k, v in (d.get("headers") or {}).items())
    body = d.get("request_body")
    body_str = f"-d '{body}'" if body else ""
    curl = f"curl -X {d['method']} '{d['api_endpoint']}' {header_str} {body_str}".strip()
    return {"ok": True, "curl": curl}


@router.get("/export/interface/")
async def export_interface(tc_id: str = Query(default=""), _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_testcase(tc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="用例不存在")
    d = rec.to_dict()
    return {
        "ok": True,
        "interface": {
            "method": d["method"],
            "path": d["api_endpoint"],
            "summary": d["title"],
            "headers": d.get("headers"),
            "request_body": d.get("request_body"),
        },
    }


@router.post("/request-history/")
async def save_request(payload: DebugPayload, user: dict = Depends(require_auth)):
    """保存调试请求到历史。"""
    store = get_task_store()
    rec = store.save_request_history({
        "title": f"{payload.method} {payload.url}",
        "method": payload.method,
        "url": payload.url,
        "headers": _dump(payload.headers),
        "body": payload.body,
    }, user_id=user.get("username", ""))
    return {"ok": True, **rec}


@router.get("/request-history/list/")
async def list_request_history(_: None = Depends(require_auth)):
    store = get_task_store()
    items = store.list_request_history()
    return {"items": items, "total": len(items)}


@router.get("/request-history/{rh_id}/")
async def get_request(rh_id: str, _: None = Depends(require_auth)):
    store = get_task_store()
    rec = store.get_request_history(rh_id)
    if not rec:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    return rec
