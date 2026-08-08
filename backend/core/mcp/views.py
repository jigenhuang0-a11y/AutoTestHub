"""
MCP REST API 视图 — 为编排服务提供 HTTP 接口

编排服务通过 HTTP 调用这些端点来发现和调用工具，替代硬编码的 AGENT_REGISTRY。

端点：
    GET  /api/mcp/tools/list/?team_id=xxx   → 列出工具
    POST /api/mcp/tools/call/                → 调用工具
    GET  /api/mcp/server/info/               → 服务器信息
    GET  /api/mcp/health/                    → 健康检查
"""
import json
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from core.tool_gateway.gateway import get_tool_gateway

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_tools(request):
    """
    列出工具 — 对应 MCP tools/list

    GET /api/mcp/tools/list/?team_id=team_a&format=openai

    Query参数:
        team_id: 团队ID（可选，默认返回全局工具）
        format: "openai" 返回 OpenAI Function Calling 格式（默认返回 MCP 格式）
    """
    team_id = request.query_params.get('team_id') or request.user.id
    output_format = request.query_params.get('format', 'mcp')

    gateway = get_tool_gateway()

    if output_format == 'openai':
        tools = gateway.get_tools_for_agent(team_id=str(team_id))
        return Response({"tools": tools, "count": len(tools)})

    tools = gateway.list_tools(team_id=str(team_id))
    return Response({"tools": tools, "count": len(tools)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def call_tool(request):
    """
    调用工具 — 对应 MCP tools/call

    POST /api/mcp/tools/call/
    {
        "name": "knowledge_search",
        "arguments": {"query": "登录接口"},
        "team_id": "team_a"      // 可选
    }
    """
    name = request.data.get('name', '')
    arguments = request.data.get('arguments', {})
    team_id = request.data.get('team_id') or str(request.user.id)

    if not name:
        return Response(
            {"error": "工具名不能为空"}, status=status.HTTP_400_BAD_REQUEST
        )

    gateway = get_tool_gateway()
    result = gateway.call_tool(
        name=name,
        arguments=arguments,
        team_id=team_id,
        user_id=request.user.id,
    )

    if result.get("isError"):
        return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def server_info(request):
    """
    服务器信息 — 对应 MCP server/info

    GET /api/mcp/server/info/
    """
    gateway = get_tool_gateway()
    return Response({
        "name": "AutoTestHub MCP Server",
        "version": "1.0.0",
        "protocolVersion": "2024-11-05",
        "gateway": gateway.health(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_records(request):
    """
    审计记录查询

    GET /api/mcp/audit/?team_id=team_a&tool_name=knowledge_search&limit=50
    """
    team_id = request.query_params.get('team_id')
    tool_name = request.query_params.get('tool_name')
    limit = int(request.query_params.get('limit', 50))

    gateway = get_tool_gateway()
    records = gateway.get_audit_records(
        team_id=team_id, tool_name=tool_name, limit=limit
    )
    stats = gateway.get_audit_stats(team_id=team_id)

    return Response({"records": records, "stats": stats})


@api_view(['GET'])
def mcp_health(request):
    """
    MCP 健康检查（无需认证）

    GET /api/mcp/health/
    """
    gateway = get_tool_gateway()
    return Response({
        "status": "ok" if gateway._enabled else "disabled",
        "gateway": gateway.health(),
    })
