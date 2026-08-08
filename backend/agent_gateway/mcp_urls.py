"""
MCP API 路由（ToolGateway 增强版）

GET  /api/mcp/tools/            → 列出所有工具（支持 team_id + format）
POST /api/mcp/tools/call/       → 调用工具（含权限 + 审计）
POST /api/mcp/tools/sse/        → SSE 流式工具调用
GET  /api/mcp/server/info/      → 服务器信息 + Gateway 状态
POST /api/mcp/handle/           → JSON-RPC 处理
GET  /api/mcp/tools/<tool>/schema/ → 工具 Schema
GET  /api/mcp/audit/            → 审计记录查询
GET  /api/mcp/health/           → 健康检查（无需认证）
"""
from django.urls import path
from .mcp_views import (
    mcp_list_tools, mcp_call_tool, mcp_sse_stream,
    mcp_server_info, mcp_handle_jsonrpc, mcp_tool_schema,
    mcp_audit_records, mcp_health,
)

urlpatterns = [
    path('tools/', mcp_list_tools, name='mcp-list-tools'),
    path('tools/call/', mcp_call_tool, name='mcp-call-tool'),
    path('tools/sse/', mcp_sse_stream, name='mcp-sse-stream'),
    path('server/info/', mcp_server_info, name='mcp-server-info'),
    path('handle/', mcp_handle_jsonrpc, name='mcp-jsonrpc'),
    path('tools/<str:tool_name>/schema/', mcp_tool_schema, name='mcp-tool-schema'),
    path('audit/', mcp_audit_records, name='mcp-audit'),
    path('health/', mcp_health, name='mcp-health'),
]
