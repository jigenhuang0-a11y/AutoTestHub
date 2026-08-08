"""
MCP 工具网关接口

Phase 2.4：工具列表持久化到 SQLite，替换 MOCK_TOOLS 内存数据。
真实沙箱执行（code_runner / sql_executor）保持不变，
审计日志保留内存 mock（后期可持久化到审计表）。
"""
import logging
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.v1.endpoints.auth import require_non_viewer
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# 沙箱模块（可能不存在，找不到时回退 mock）
_SANDBOX_AVAILABLE = False
_SandboxExecutor = None
_SandboxConfig = None
_SandboxResult = None
try:
    from app.core.sandbox import SandboxExecutor, SandboxConfig, SandboxResult
    _SandboxExecutor = SandboxExecutor
    _SandboxConfig = SandboxConfig
    _SandboxResult = SandboxResult
    _SANDBOX_AVAILABLE = True
    logger.info("[MCP] 沙箱模块加载成功，code_runner / sql_executor 将走真实隔离执行")
except ImportError as e:
    logger.warning(f"[MCP] 沙箱模块不可用，code_runner / sql_executor 将回退 mock: {e}")

from app.api.v1.endpoints.auth import require_admin
from app.core.task_store import get_task_store

router = APIRouter(dependencies=[Depends(require_admin)])

TOOL_STATUS = ["active", "disabled"]
TOOL_CATEGORIES = ["search", "file", "database", "code", "browser", "notify"]


class MCPItem(BaseModel):
    id: str
    name: str
    category: str
    description: str
    endpoint: str
    status: str
    success_rate: int
    avg_latency_ms: int
    call_count: int


class MCPAuditItem(BaseModel):
    id: str
    tool_name: str
    status: str
    duration_ms: int
    request_preview: str
    response_preview: str
    created_at: str


class MCPToolCall(BaseModel):
    tool_name: str
    arguments: dict


class MCPToolCallResult(BaseModel):
    tool_name: str
    status: str
    result: str
    duration_ms: int


MOCK_AUDITS = []  # 审计日志暂留内存（后期可迁至 mcp_audits 表）


def _generate_audit(count: int = 20) -> list[MCPAuditItem]:
    store = get_task_store()
    tools = store.list_mcp_tools()
    if not tools:
        return []
    audits = []
    for i in range(count):
        tool = random.choice(tools)
        status = "success" if random.random() > 0.1 else "failed"
        created = datetime.now() - timedelta(
            minutes=random.randint(1, 60 * 24 * 2)
        )
        audits.append(
            MCPAuditItem(
                id=f"audit-{uuid.uuid4().hex[:8]}",
                tool_name=tool["name"],
                status=status,
                duration_ms=random.randint(20, 1000),
                request_preview=f'{{"query": "example {i}"}}',
                response_preview="{\"result\": \"ok\"}" if status == "success" else "{\"error\": \"timeout\"}",
                created_at=created.isoformat(),
            )
        )
    return sorted(audits, key=lambda x: x.created_at, reverse=True)


# 首次加载审计 mock
if not MOCK_AUDITS:
    MOCK_AUDITS.extend(_generate_audit(30))


class MCPItemCreate(BaseModel):
    name: str
    category: str
    description: str = ""
    input_schema: dict = {}
    endpoint: str = ""
    enabled: bool = True


@router.get("/tools/", response_model=dict)
async def list_tools(category: Optional[str] = None):
    """获取 MCP 工具列表，支持按分类过滤。"""
    store = get_task_store()
    tools = store.list_mcp_tools(category=category or "")
    return {"count": len(tools), "results": tools}


@router.get("/tools/categories/", response_model=dict)
async def list_categories():
    """获取工具分类列表（含每个分类的工具数量和激活状态）。"""
    store = get_task_store()
    tools = store.list_mcp_tools()
    result = []
    for cat_name in TOOL_CATEGORIES:
        cat_tools = [t for t in tools if getattr(t, "category", "") == cat_name]
        result.append({
            "name": cat_name,
            "label": _category_label(cat_name),
            "count": len(cat_tools),
            "active": any(getattr(t, "status", "active") == "active" for t in cat_tools),
        })
    return {"results": result}


@router.post("/tools/", response_model=dict)
async def create_tool(payload: MCPItemCreate, user: dict = Depends(require_non_viewer)):
    """新增 MCP 工具（持久化到 SQLite）。"""
    if payload.category not in TOOL_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"不支持的工具分类: {payload.category}")

    store = get_task_store()
    existing = store.get_mcp_tool(payload.name)
    if existing:
        raise HTTPException(status_code=400, detail="工具名称已存在")

    record = store.create_mcp_tool(
        name=payload.name,
        category=payload.category,
        description=payload.description,
        endpoint=payload.endpoint,
        status="active" if payload.enabled else "disabled",
        input_schema=payload.input_schema,
    )
    return {"id": record.tool_id, "name": record.name, "message": "created"}


class MCPItemUpdate(BaseModel):
    """MCP 工具更新字段（均为可选）"""
    status: Optional[str] = None       # "active" | "disabled"
    description: Optional[str] = None
    endpoint: Optional[str] = None
    category: Optional[str] = None


@router.put("/tools/{tool_name}/", response_model=dict)
async def update_tool(tool_name: str, payload: MCPItemUpdate, user: dict = Depends(require_non_viewer)):
    """更新 MCP 工具（状态切换 / 字段修改）。"""
    if payload.status and payload.status not in TOOL_STATUS:
        raise HTTPException(status_code=400, detail=f"无效状态: {payload.status}")

    store = get_task_store()
    record = store.update_mcp_tool(
        name=tool_name,
        status=payload.status,
        description=payload.description,
        endpoint=payload.endpoint,
        category=payload.category,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="工具不存在")

    return {
        "name": record.name,
        "status": record.status,
        "description": record.description,
        "message": "updated",
    }


@router.delete("/tools/{tool_name}/", response_model=dict)
async def delete_tool(tool_name: str, user: dict = Depends(require_non_viewer)):
    """删除 MCP 工具。"""
    store = get_task_store()
    deleted = store.delete_mcp_tool(tool_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="工具不存在")
    return {"name": tool_name, "status": "deleted"}


@router.post("/tools/call/", response_model=MCPToolCallResult)
async def call_tool(payload: MCPToolCall):
    """调用 MCP 工具。

    code_runner / sql_executor → 真实沙箱隔离执行
    其他工具 → mock 返回
    """
    store = get_task_store()
    t0 = time.time()

    # 工具调用计数
    store.bump_mcp_tool_call(payload.tool_name)

    # ---------- 走真实沙箱 ----------
    if payload.tool_name in ("code_runner", "sql_executor") and _SANDBOX_AVAILABLE:
        code = _extract_code_from_args(payload.tool_name, payload.arguments)
        if not code:
            duration_ms = int((time.time() - t0) * 1000)
            _log_audit(payload.tool_name, "error", duration_ms, str(payload.arguments)[:120], "未提供代码/脚本内容")
            return MCPToolCallResult(
                tool_name=payload.tool_name,
                status="error",
                result="参数中缺少可执行代码，请提供 'code' 或 'script' 字段",
                duration_ms=duration_ms,
            )

        sandbox_timeout = payload.arguments.get("timeout", 300) if isinstance(payload.arguments, dict) else 300
        sandbox_memory = payload.arguments.get("max_memory_mb", 512) if isinstance(payload.arguments, dict) else 512

        config = _SandboxConfig(
            timeout_seconds=sandbox_timeout,
            max_memory_mb=sandbox_memory,
        )
        executor = _SandboxExecutor(config)
        result = executor.run_script(script_content=code, filename="mcp_tool.py")

        duration_ms = int((time.time() - t0) * 1000)
        status = "success" if result.ok else result.status.value
        response_text = result.stdout if result.ok else (result.error_message or result.stderr)
        _log_audit(payload.tool_name, status, duration_ms, code[:120], (response_text or "")[:200])

        return MCPToolCallResult(
            tool_name=payload.tool_name,
            status=status,
            result=f"[沙箱执行 {result.status.value}]\n{response_text}",
            duration_ms=duration_ms,
        )

    # ---------- 回退：mock ----------
    duration = random.randint(50, 500)
    _log_audit(payload.tool_name, "success", duration, str(payload.arguments)[:120], "mock result")
    return MCPToolCallResult(
        tool_name=payload.tool_name,
        status="success",
        result=f"工具 {payload.tool_name} 执行成功（mock）",
        duration_ms=duration,
    )


# ============================================================
# 辅助函数
# ============================================================

def _extract_code_from_args(tool_name: str, arguments: dict) -> str:
    """从工具调用参数中提取可执行代码/脚本。"""
    if not isinstance(arguments, dict):
        return ""
    if tool_name == "code_runner":
        return arguments.get("code") or arguments.get("script") or arguments.get("source") or ""
    if tool_name == "sql_executor":
        return arguments.get("sql") or arguments.get("query") or ""
    return ""


def _log_audit(tool_name: str, status: str, duration_ms: int, request_preview: str, response_preview: str):
    """写入审计日志（内存 mock，后期可迁至 DB）。"""
    MOCK_AUDITS.append(
        MCPAuditItem(
            id=f"audit-{uuid.uuid4().hex[:8]}",
            tool_name=tool_name,
            status=status,
            duration_ms=duration_ms,
            request_preview=request_preview,
            response_preview=response_preview,
            created_at=datetime.now().isoformat(),
        )
    )


_CATEGORY_LABELS = {
    "search": "搜索工具",
    "file": "文件处理",
    "database": "数据库",
    "code": "代码执行",
    "browser": "浏览器",
    "notify": "通知工具",
}


def _category_label(cat: str) -> str:
    """分类中文标签"""
    return _CATEGORY_LABELS.get(cat, cat)


@router.get("/audit/", response_model=dict)
async def list_audit(
    tool_name: Optional[str] = None,
    status: Optional[str] = None,
):
    """获取 MCP 审计日志（内存 mock）。"""
    items = MOCK_AUDITS
    if tool_name:
        items = [a for a in items if a.tool_name == tool_name]
    if status:
        items = [a for a in items if a.status == status]
    return {"count": len(items), "results": [a.model_dump() for a in items[:50]]}
