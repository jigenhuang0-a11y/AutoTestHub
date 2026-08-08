"""
底座工具注册/发现端点

提供双向 MCP 注册的关键能力：
1. POST /register — 接收 Django 启动时推送的工具注册
2. POST /refresh — Django 工具变更后触发底座即时刷新
3. GET  /status  — 查询工具缓存状态
4. GET  /orchestrator/tools — 暴露底座编排能力为 MCP 元工具
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

logger = logging.getLogger(__name__)

from app.api.v1.endpoints.auth import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])

# ============================================================
# 工具注册：接收 Django 推送
# ============================================================


@router.post("/register", response_model=ToolRegisterResponse)
async def register_tools(payload: ToolBatchRegister):
    """
    接收 Django 推送的工具批量注册

    Django 启动时调用此端点，主动注册所有可用工具。
    底座将工具信息写入全局 ToolDiscovery 单例缓存，
    所有 workflow 实例共享同一份工具列表。

    后续：Django 工具变更时也会调用此端点触发更新。
    """
    from app.core.tool_discovery import get_global_discovery

    discovery = get_global_discovery()

    # 将 Pydantic 模型转为 dict
    tool_dicts = []
    for tool_item in payload.tools:
        tool_dicts.append({
            "name": tool_item.name,
            "description": tool_item.description,
            "inputSchema": tool_item.input_schema,
            "category": tool_item.category,
            "owner_team_id": tool_item.owner_team_id,
        })

    # 使用 bulk_register 批量写入全局缓存
    result = discovery.bulk_register(tool_dicts)

    logger.info(
        f"[ToolRegistry] 收到 Django 工具注册 (全局单例): "
        f"新增={result['registered']}, 更新={result['updated']}"
    )

    return ToolRegisterResponse(
        registered=result["registered"],
        updated=result["updated"],
        failed=len(result.get("errors", [])),
        errors=result.get("errors", []),
    )


@router.post("/refresh", response_model=dict)
async def refresh_tools(payload: Optional[ToolRefreshRequest] = None):
    """
    触发工具即时刷新

    Django 工具变更（新增/删除/更新）后调用此端点，
    触发底座立即从 Django MCP API 拉取最新工具列表。
    """
    from app.core.tool_discovery import get_global_discovery

    force = payload.force if payload else True
    team_id = payload.team_id if payload else None

    discovery = get_global_discovery()

    if force:
        result = discovery.force_refresh(team_id=team_id)
    else:
        if discovery.is_stale():
            result = discovery.force_refresh(team_id=team_id)
        else:
            result = {
                "refreshed": False,
                "tool_count": len(discovery._tools),
                "agent_mappings": len(discovery._agent_map),
            }

    result["force"] = force
    return result


@router.get("/status", response_model=ToolStatusResponse)
async def tool_status():
    """
    查询工具缓存状态

    返回全局 ToolDiscovery 单例的健康状态和缓存信息。
    """
    from app.core.tool_discovery import get_global_discovery

    discovery = get_global_discovery()
    health = discovery.health()
    discovery_healthy = len(discovery._tools) > 0

    return ToolStatusResponse(
        total_tools=health.get("tools_count", 0),
        agent_mappings=health.get("agent_mappings", 0),
        last_refresh=health.get("last_refresh", 0),
        is_stale=health.get("stale", True),
        discovery_healthy=discovery_healthy,
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
    暴露底座编排能力为 MCP 工具列表

    Django 侧 Agent 可以调用此端点发现底座的编排能力，
    实现"双向注册"——底座也能作为工具提供方被 Django 发现。
    """
    return {
        "server": "AutoTestHub Orchestrator MCP",
        "version": "1.0.0",
        "tools": ORCHESTRATOR_MCP_TOOLS,
        "count": len(ORCHESTRATOR_MCP_TOOLS),
    }
