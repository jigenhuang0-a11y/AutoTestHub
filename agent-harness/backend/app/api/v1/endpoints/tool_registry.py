"""
底座工具注册/发现端点

Django 已移除。工具在进程内由 app/tools/* 模块自注册（见 app/tools/registry.py）。
本端点暴露：
1. GET  /status             — 查询本地工具注册表状态
2. POST /register           — 可选：人工注册额外工具到本地注册表
3. GET  /orchestrator/tools — 暴露底座编排能力为 MCP 元工具
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends

from app.schemas.tool_registry import (
    ToolBatchRegister,
    ToolRegisterResponse,
    ToolRefreshRequest,
    ToolStatusResponse,
)
from app.tools.registry import get_registry

logger = logging.getLogger(__name__)

from app.api.v1.endpoints.auth import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


@router.post("/register", response_model=ToolRegisterResponse)
async def register_tools(payload: ToolBatchRegister):
    """
    人工注册工具到本地注册表。

    工具主路径由 app/tools/* 模块在 import 时自动注册；
    此端点用于运行时动态追加（如插件式工具）。
    """
    registry = get_registry()
    registered = 0
    updated = 0
    errors = []

    for tool_item in payload.tools:
        try:
            existing = registry.get(tool_item.name)
            if existing:
                updated += 1
            else:
                registered += 1
            registry.register(
                name=tool_item.name,
                description=tool_item.description,
                input_schema=tool_item.input_schema,
                handler=lambda **kw: {"status": "success", "data": {}, "note": "manual"},
                category=tool_item.category,
                owner_team_id=tool_item.owner_team_id,
            )
        except Exception as e:
            errors.append({"name": tool_item.name, "error": str(e)})

    return ToolRegisterResponse(
        registered=registered,
        updated=updated,
        failed=len(errors),
        errors=errors,
    )


@router.post("/refresh", response_model=dict)
async def refresh_tools(payload: Optional[ToolRefreshRequest] = None):
    """
    触发工具即时刷新（本地注册表无需远程拉取，返回当前快照）。
    """
    registry = get_registry()
    health = registry.health()
    return {
        "refreshed": True,
        "tool_count": health["tools_count"],
        "agent_mappings": health["agent_mappings"],
        "force": True,
    }


@router.get("/status", response_model=ToolStatusResponse)
async def tool_status():
    """
    查询本地工具注册表状态。
    """
    registry = get_registry()
    health = registry.health()
    return ToolStatusResponse(
        total_tools=health.get("tools_count", 0),
        agent_mappings=health.get("agent_mappings", 0),
        last_refresh=health.get("last_refresh", 0),
        is_stale=False,
        discovery_healthy=health["tools_count"] > 0,
    )


# ============================================================
# 编排能力 MCP 元工具：底座将自身编排能力暴露为 MCP 协议
# ============================================================

ORCHESTRATOR_MCP_TOOLS = [
    {
        "name": "workflow_invoke",
        "description": "调用 AI 编排工作流（Plan→Orchestrate→Verify），执行多步 Agent 任务",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_request": {"type": "string", "description": "用户需求描述"},
                "team_id": {"type": "string", "description": "团队 ID", "default": "default"},
                "template_id": {"type": "string", "description": "工作流模板 ID（可选）"},
                "stream": {"type": "boolean", "description": "是否流式返回", "default": False},
            },
            "required": ["user_request"],
        },
        "category": "orchestration",
        "endpoint": "/api/v1/workflow/invoke",
        "method": "POST",
    },
    {
        "name": "llm_chat",
        "description": "调用 LLM 模型进行对话/推理/生成",
        "inputSchema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                            "content": {"type": "string"},
                        },
                    },
                },
                "task_type": {"type": "string", "description": "任务类型（planning/code_generation/evaluation/fast_chat）"},
                "model": {"type": "string", "description": "指定模型（可选）"},
            },
            "required": ["messages"],
        },
        "category": "orchestration",
        "endpoint": "/api/v1/llm/chat",
        "method": "POST",
    },
    {
        "name": "memory_store",
        "description": "存储会话记忆到长期记忆库",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队 ID"},
                "user_id": {"type": "string", "description": "用户 ID"},
                "content": {"type": "object", "description": "记忆内容"},
                "session_id": {"type": "string", "description": "会话 ID"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "标签"},
            },
            "required": ["team_id", "content"],
        },
        "category": "orchestration",
        "endpoint": "/api/v1/memory/store",
        "method": "POST",
    },
    {
        "name": "memory_search",
        "description": "从长期记忆库中搜索相关记忆",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队 ID"},
                "query": {"type": "string", "description": "搜索查询"},
                "top_k": {"type": "integer", "description": "返回条数", "default": 5},
            },
            "required": ["team_id", "query"],
        },
        "category": "orchestration",
        "endpoint": "/api/v1/memory/search",
        "method": "GET",
    },
    {
        "name": "template_list",
        "description": "列出团队可用的工作流模板",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "string", "description": "团队 ID"},
                "status": {"type": "string", "description": "模板状态（draft/published/archived）"},
            },
            "required": ["team_id"],
        },
        "category": "orchestration",
        "endpoint": "/api/v1/templates/",
        "method": "GET",
    },
]


@router.get("/orchestrator/tools", response_model=dict)
async def orchestrator_mcp_tools():
    """
    暴露底座编排能力为 MCP 工具列表。
    """
    return {
        "server": "AutoTestHub Orchestrator MCP",
        "version": "1.0.0",
        "tools": ORCHESTRATOR_MCP_TOOLS,
        "count": len(ORCHESTRATOR_MCP_TOOLS),
    }
