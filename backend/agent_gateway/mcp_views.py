"""
MCP 工具调用 API 端点（接入 ToolGateway 权限+审计）

提供 HTTP REST 接口供前端/Agent/编排服务调用 MCP 工具

路由:
    GET  /api/mcp/tools/           — 列出所有工具（支持 team_id + format）
    POST /api/mcp/tools/call/      — 调用工具（含权限检查 + 审计）
    GET  /api/mcp/tools/sse/       — SSE 流式工具调用
    GET  /api/mcp/server/info/     — 服务器信息 + Gateway 状态
    POST /api/mcp/handle/          — JSON-RPC 处理
    GET  /api/mcp/tools/{tool}/schema/ — 工具 Schema
    GET  /api/mcp/audit/           — 审计记录查询
    GET  /api/mcp/health/          — 健康检查（无需认证）
"""
import json
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.http import StreamingHttpResponse

from core.mcp.server import get_mcp_server
from core.mcp.tools_adapter import register_all_tools
from core.mcp.transport import SSETransport
from core.tool_gateway.gateway import get_tool_gateway

logger = logging.getLogger(__name__)


def _ensure_tools_registered(user_id: int = None):
    """确保工具已注册到全局 MCP Server"""
    server = get_mcp_server()
    if server.get_stats()["tools_registered"] == 0:
        register_all_tools(server, user_id=user_id)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mcp_list_tools(request):
    """
    列出所有 MCP 工具

    GET /api/mcp/tools/?team_id=xxx&format=openai

    支持 Gateway 权限过滤：只返回当前团队有权限的工具
    """
    _ensure_tools_registered(request.user.id)
    team_id = request.query_params.get('team_id') or str(request.user.id)
    output_format = request.query_params.get('format', 'mcp')

    gateway = get_tool_gateway()

    if output_format == 'openai':
        tools = gateway.get_tools_for_agent(team_id=team_id)
        return Response({"tools": tools, "count": len(tools)})

    tools = gateway.list_tools(team_id=team_id)
    categories = list(set(t.get("category", "general") for t in tools))

    return Response({
        "count": len(tools),
        "tools": tools,
        "categories": categories,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mcp_call_tool(request):
    """
    调用 MCP 工具（含 ToolGateway 权限检查 + 审计）

    POST /api/mcp/tools/call/
    {
        "tool": "testcase_search",         // 或 "name" (兼容 MCP 规范)
        "arguments": {"query": "登录", "limit": 10},
        "team_id": "team_a"                // 可选
    }
    """
    tool_name = request.data.get("tool") or request.data.get("name", "")
    arguments = request.data.get("arguments", {})
    team_id = request.data.get("team_id") or str(request.user.id)

    if not tool_name:
        return Response({"error": "tool 或 name 参数不能为空"}, status=status.HTTP_400_BAD_REQUEST)

    _ensure_tools_registered(request.user.id)
    server = get_mcp_server()
    result = server.call_tool(
        tool_name, arguments,
        team_id=team_id,
        user_id=request.user.id,
    )

    return Response({
        "tool": tool_name,
        "result": result,
        "is_error": result.get("isError", False),
    })



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mcp_sse_stream(request):
    """
    SSE 流式 MCP 工具调用

    POST /api/mcp/tools/sse/
    (请求体为多行 JSON，每行一个事件)

    事件格式:
        {"type": "tools/call", "data": {"name": "testcase_search", "arguments": {...}}}
        {"type": "tools/list"}
    """
    _ensure_tools_registered(request.user.id)
    server = get_mcp_server()
    transport = SSETransport(server)

    response = StreamingHttpResponse(
        transport.stream_response(request.body),
        content_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mcp_server_info(request):
    """
    MCP 服务器信息 + ToolGateway 状态

    GET /api/mcp/server/info/
    """
    server = get_mcp_server()
    info = server.handle_request("server/info")
    gateway = get_tool_gateway()
    info["gateway"] = gateway.health()
    return Response(info)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mcp_audit_records(request):
    """
    审计记录查询

    GET /api/mcp/audit/?team_id=xxx&tool_name=knowledge_search&limit=50
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
@permission_classes([AllowAny])
def mcp_health(request):
    """
    MCP + Gateway 健康检查（无需认证）

    GET /api/mcp/health/
    """
    server = get_mcp_server()
    gateway = get_tool_gateway()
    return Response({
        "status": "ok" if gateway._enabled else "disabled",
        "mcp": {
            "name": server.name,
            "version": server.version,
            "stats": server.get_stats(),
        },
        "gateway": gateway.health(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mcp_handle_jsonrpc(request):
    """
    JSON-RPC 2.0 格式处理

    POST /api/mcp/handle/
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "testcase_search", "arguments": {"query": "登录"}}
    }
    """
    _ensure_tools_registered(request.user.id)
    server = get_mcp_server()

    method = request.data.get("method", "")
    params = request.data.get("params", {})
    req_id = request.data.get("id")

    try:
        result = server.handle_request(method, params)
        return Response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        })
    except Exception as e:
        return Response({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32603, "message": str(e)},
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mcp_tool_schema(request, tool_name: str):
    """
    获取单个工具的 Schema

    GET /api/mcp/tools/{tool_name}/schema/
    """
    _ensure_tools_registered(request.user.id)
    server = get_mcp_server()
    tool = server.get_tool(tool_name)

    if not tool:
        return Response({"error": f"工具 '{tool_name}' 未找到"}, status=status.HTTP_404_NOT_FOUND)

    return Response(tool.to_dict())
